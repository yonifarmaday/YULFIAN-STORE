import html
import json
import datetime as dt

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Yulfian Store Frozen", page_icon="❄️", layout="wide")

rp = lambda n: "Rp" + f"{int(n or 0):,}".replace(",", ".")
ROLES = {"owner": "Pemilik", "kasir": "Kasir", "member": "Member"}

try:
    LIVE = "supabase" in st.secrets  # tanpa secrets -> mode pratinjau
except Exception:
    LIVE = False


# ---------------------------------------------------------------- data: pratinjau
class Demo:
    """Data contoh di memori sesi. Hilang saat sesi berakhir."""

    def __init__(self):
        ss = st.session_state
        if "demo" not in ss:
            ss.demo = {
                "p": [
                    {"id": 1, "nama": "Nugget ayam 500 g", "harga": 38000, "stok": 24, "h": [35000, 38000]},
                    {"id": 2, "nama": "Sosis sapi 1 kg", "harga": 62000, "stok": 15, "h": [62000]},
                    {"id": 3, "nama": "Bakso sapi 500 g", "harga": 35000, "stok": 30, "h": [32000, 35000]},
                    {"id": 4, "nama": "Kentang goreng 1 kg", "harga": 45000, "stok": 18, "h": [45000]},
                    {"id": 5, "nama": "Dimsum ayam isi 10", "harga": 28000, "stok": 22, "h": [25000, 28000]},
                    {"id": 6, "nama": "Udang kupas 500 g", "harga": 70000, "stok": 9, "h": [75000, 70000]},
                ],
                "m": [
                    {"id": 1, "nama": "Bu Sari", "hp": "0812-3456-7890", "poin": 42, "hutang": 85000},
                    {"id": 2, "nama": "Pak Andi", "hp": "0857-1122-3344", "poin": 17, "hutang": 0},
                    {"id": 3, "nama": "Warung Mbak Rina", "hp": "0821-9988-7766", "poin": 120, "hutang": 240000},
                ],
                "s": [
                    {"t": "08:12", "m": "Bu Sari", "total": 112000, "metode": "tunai"},
                    {"t": "10:05", "m": "Warung Mbak Rina", "total": 240000, "metode": "hutang"},
                ],
                "n": 100,
            }
        self.d = ss.demo

    def _id(self):
        self.d["n"] += 1
        return self.d["n"]

    def products(self):
        return self.d["p"]

    def add_product(self, nama, harga, stok):
        self.d["p"].append({"id": self._id(), "nama": nama, "harga": harga, "stok": stok, "h": [harga]})

    def set_price(self, pid, harga):
        p = next(x for x in self.d["p"] if x["id"] == pid)
        p["harga"] = harga
        p["h"].append(harga)

    def update_product(self, pid, nama, harga):
        p = next(x for x in self.d["p"] if x["id"] == pid)
        p["nama"] = nama
        if harga != p["harga"]:
            self.set_price(pid, harga)

    def price_history(self, pid):
        h = next(x for x in self.d["p"] if x["id"] == pid)["h"]
        return [{"Perubahan": "Harga awal" if i == 0 else f"Ke-{i}",
                 "Harga lama": rp(h[i - 1]) if i else "-", "Harga baru": rp(v)} for i, v in enumerate(h)][::-1]

    def members(self):
        return self.d["m"]

    def my_member(self):
        return self.d["m"][0]

    def add_member(self, nama, hp):
        self.d["m"].append({"id": self._id(), "nama": nama, "hp": hp, "poin": 0, "hutang": 0})

    def checkout(self, mid, items, bayar, metode):
        byid = {p["id"]: p for p in self.d["p"]}
        total = sum(byid[i["product_id"]]["harga"] * i["qty"] for i in items)
        poin = total // 10000 if mid else 0
        m = next((x for x in self.d["m"] if x["id"] == mid), None)
        if m:
            m["poin"] += poin
            if metode == "hutang":
                m["hutang"] += total
        for i in items:
            byid[i["product_id"]]["stok"] -= i["qty"]
        self.d["s"].insert(0, {"t": dt.datetime.now().strftime("%H:%M"), "m": m["nama"] if m else "Umum",
                               "total": total, "metode": metode})
        return {"total": total, "poin": poin}

    def pay_debt(self, mid, jumlah):
        m = next(x for x in self.d["m"] if x["id"] == mid)
        m["hutang"] = max(0, m["hutang"] - jumlah)

    def sales_today(self):
        return [{"waktu": s["t"], "member": s["m"], "total": s["total"], "metode": s["metode"]} for s in self.d["s"]]

    def week(self):
        hari = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab"]
        data = [820000, 640000, 910000, 760000, 1020000, 880000]
        hari.append("Hari ini")
        data.append(sum(s["total"] for s in self.d["s"]))
        return pd.DataFrame({"Omzet": data}, index=hari)

    def my_sales(self):
        n = self.my_member()["nama"]
        return [{"waktu": s["t"], "total": s["total"], "poin": s["total"] // 10000} for s in self.d["s"] if s["m"] == n]


# ---------------------------------------------------------------- data: Supabase
class Sb:
    """Memakai sesi login pengguna, sehingga aturan RLS di schema.sql berlaku."""

    def __init__(self):
        self.c = st.session_state.sbc

    def products(self):
        return self.c.table("products").select("*").eq("aktif", True).order("nama").execute().data

    def add_product(self, nama, harga, stok):
        self.c.table("products").insert({"nama": nama, "harga": harga, "stok": stok}).execute()

    def set_price(self, pid, harga):
        self.c.table("products").update({"harga": harga}).eq("id", pid).execute()

    def update_product(self, pid, nama, harga):
        self.c.table("products").update({"nama": nama, "harga": harga}).eq("id", pid).execute()

    def price_history(self, pid):
        r = self.c.table("price_history").select("*").eq("product_id", pid).order("dibuat", desc=True).execute().data
        return [{"Waktu": x["dibuat"][:16].replace("T", " "),
                 "Harga lama": rp(x["harga_lama"]) if x["harga_lama"] is not None else "-",
                 "Harga baru": rp(x["harga_baru"])} for x in r]

    def members(self):
        return self.c.table("members").select("*").order("nama").execute().data

    def my_member(self):
        return self.c.table("members").select("*").eq("user_id", st.session_state.me["id"]).single().execute().data

    def add_member(self, nama, hp):
        self.c.table("members").insert({"nama": nama, "hp": hp}).execute()

    def checkout(self, mid, items, bayar, metode):
        r = self.c.rpc("checkout", {"p_member": mid, "p_items": items, "p_bayar": bayar, "p_metode": metode}).execute().data
        total = sum(next(p["harga"] for p in self.products() if p["id"] == i["product_id"]) * i["qty"] for i in items)
        return {"total": total, "poin": r["poin"]}

    def pay_debt(self, mid, jumlah):
        self.c.rpc("bayar_hutang", {"p_member": mid, "p_jumlah": jumlah}).execute()

    def _sales(self, since):
        return self.c.table("sales").select("total,metode,dibuat,members(nama)").gte("dibuat", since.isoformat()).order(
            "dibuat", desc=True).execute().data

    def sales_today(self):
        mulai = dt.datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        return [{"waktu": s["dibuat"][11:16], "member": (s["members"] or {}).get("nama", "Umum"),
                 "total": s["total"], "metode": s["metode"]} for s in self._sales(mulai)]

    def week(self):
        mulai = (dt.datetime.now().astimezone() - dt.timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        df = pd.DataFrame(self._sales(mulai))
        if df.empty:
            return pd.DataFrame({"Omzet": [0]}, index=["-"])
        df["tgl"] = df["dibuat"].str[:10]
        return df.groupby("tgl")["total"].sum().to_frame("Omzet")

    def my_sales(self):
        r = self.c.table("sales").select("total,poin,dibuat").order("dibuat", desc=True).limit(20).execute().data
        return [{"waktu": s["dibuat"][:10], "total": s["total"], "poin": s["poin"]} for s in r]


# ---------------------------------------------------------------- struk
def receipt_text(items, total, bayar, metode, member, poin):
    w, garis = 32, "-" * 32
    kiri_kanan = lambda a, b: a + b.rjust(max(1, w - len(a)))
    t = ["YULFIAN STORE FROZEN", dt.datetime.now().strftime("%d/%m/%Y %H:%M"), garis]
    for i in items:
        t += [i["nama"][:w], kiri_kanan(f" {i['qty']} x {rp(i['harga'])}", rp(i["qty"] * i["harga"]))]
    t += [garis, kiri_kanan("Total", rp(total))]
    if metode == "hutang":
        t.append(kiri_kanan("Hutang", rp(total)))
    else:
        t += [kiri_kanan("Bayar", rp(bayar)), kiri_kanan("Kembali", rp(bayar - total))]
    if member:
        t += [garis, f"Member: {member}", f"Poin didapat: {poin}"]
    return "\n".join(t + ["", "Terima kasih", ""])


def print_box(text):
    """Tombol cetak: coba printer thermal Bluetooth (Web Bluetooth), jika gagal buka dialog cetak browser."""
    js = json.dumps(text)
    components.html(f"""
<button id="b" style="padding:9px 14px;border:0;border-radius:6px;background:#0b2a43;color:#fff;font:15px sans-serif;cursor:pointer">Cetak struk</button>
<pre id="r" style="font:12px monospace;margin-top:10px">{html.escape(text)}</pre>
<style>@media print{{#b{{display:none}}}}</style>
<script>
const T={js}, SV='000018f0-0000-1000-8000-00805f9b34fb';
let chr;
document.getElementById('b').onclick=async()=>{{
  try{{
    if(!chr){{
      const d=await navigator.bluetooth.requestDevice({{acceptAllDevices:true,optionalServices:[SV]}});
      const s=await (await d.gatt.connect()).getPrimaryService(SV);
      chr=(await s.getCharacteristics()).find(c=>c.properties.write||c.properties.writeWithoutResponse);
    }}
    const b=new TextEncoder().encode(T.normalize('NFD').replace(/[^\\x00-\\x7F]/g,''));
    const a=new Uint8Array([0x1b,0x40,...b,0x1d,0x56,0x00]);
    for(let i=0;i<a.length;i+=100) await chr.writeValueWithoutResponse(a.slice(i,i+100));
  }}catch(e){{chr=null;window.print();}}
}};
</script>""", height=330, scrolling=True)


# ---------------------------------------------------------------- login & peran
def new_client():
    from supabase import create_client
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])


def login():
    st.title("❄️ Yulfian Store Frozen")
    st.caption("Masuk untuk memakai kasir atau melihat poin Anda.")
    email = st.text_input("Email")
    sandi = st.text_input("Kata sandi (min. 6 karakter)", type="password")
    a, b = st.columns(2)
    if a.button("Masuk", type="primary"):
        try:
            cl = new_client()
            r = cl.auth.sign_in_with_password({"email": email, "password": sandi})
            prof = cl.table("profiles").select("*").eq("id", r.user.id).single().execute().data
            st.session_state.sbc, st.session_state.me = cl, prof
            st.rerun()
        except Exception:
            st.error("Email atau kata sandi salah.")
    if b.button("Daftar sebagai member"):
        try:
            new_client().auth.sign_up({"email": email, "password": sandi})
            st.success("Pendaftaran berhasil. Silakan masuk.")
        except Exception as e:
            st.error(str(e))


if LIVE:
    if "me" not in st.session_state:
        login()
        st.stop()
    me = st.session_state.me
    st.sidebar.write(f"{me['nama']} ({ROLES[me['role']]})")
    if st.sidebar.button("Keluar"):
        st.session_state.clear()
        st.rerun()
    D = Sb()
else:
    st.sidebar.info("Mode pratinjau: data contoh, tidak tersimpan permanen.")
    peran = st.sidebar.selectbox("Lihat sebagai", list(ROLES), format_func=ROLES.get)
    me = {"role": peran, "id": "demo", "nama": "Bu Sari"}
    D = Demo()

st.title("❄️ Yulfian Store Frozen")


# ---------------------------------------------------------------- halaman
def page_kasir():
    ss = st.session_state
    ss.setdefault("cart", {})
    produk = D.products()
    byid = {p["id"]: p for p in produk}
    kiri, kanan = st.columns([3, 2])
    with kiri:
        q = st.text_input("Cari produk")
        cols = st.columns(3)
        for i, p in enumerate([p for p in produk if q.lower() in p["nama"].lower()]):
            if cols[i % 3].button(f"{p['nama']}\n{rp(p['harga'])} · stok {p['stok']}", key=f"p{p['id']}", use_container_width=True):
                ss.cart[p["id"]] = ss.cart.get(p["id"], 0) + 1
                st.rerun()
    with kanan:
        st.subheader("Keranjang")
        if not ss.cart:
            st.caption("Klik produk untuk menambah ke keranjang.")
        for pid in list(ss.cart):
            p = byid[pid]
            ss.cart[pid] = st.number_input(f"{p['nama']} ({rp(p['harga'])})", 0, 999, ss.cart[pid], key=f"q{pid}")
            if ss.cart[pid] == 0:
                del ss.cart[pid]
                st.rerun()
        total = sum(byid[i]["harga"] * n for i, n in ss.cart.items())
        st.metric("Total", rp(total))
        opsi = {None: "Tanpa member", **{m["id"]: f"{m['nama']} · {m['poin']} poin" for m in D.members()}}
        mid = st.selectbox("Member", list(opsi), format_func=opsi.get)
        metode = st.radio("Pembayaran", ["tunai", "hutang"], horizontal=True)
        bayar = st.number_input("Uang diterima", 0, value=int(total), step=1000) if metode == "tunai" else 0
        if mid:
            st.caption(f"Poin didapat transaksi ini: {total // 10000}")
        if st.button("Bayar dan cetak struk", type="primary", disabled=not ss.cart):
            if metode == "tunai" and bayar < total:
                st.error("Uang diterima kurang dari total.")
            elif metode == "hutang" and not mid:
                st.error("Pilih member untuk penjualan hutang.")
            else:
                items = [{"product_id": i, "qty": n} for i, n in ss.cart.items()]
                baris = [{"nama": byid[i]["nama"], "qty": n, "harga": byid[i]["harga"]} for i, n in ss.cart.items()]
                try:
                    r = D.checkout(mid, items, bayar, metode)
                except Exception as e:
                    st.error(str(e))
                else:
                    ss.struk = receipt_text(baris, r["total"], bayar, metode, opsi[mid].split(" · ")[0] if mid else None, r["poin"])
                    ss.cart = {}
                    st.rerun()
    if ss.get("struk"):
        st.divider()
        st.subheader("Struk")
        print_box(ss.struk)
        if st.button("Tutup struk"):
            ss.struk = None
            st.rerun()


def page_produk():
    own = me["role"] == "owner"
    produk = D.products()
    st.dataframe(pd.DataFrame([{"Produk": p["nama"], "Harga": rp(p["harga"]), "Stok": p["stok"]} for p in produk]),
                 use_container_width=True, hide_index=True)
    nama = {p["id"]: p["nama"] for p in produk}
    if own:
        with st.expander("Tambah produk"):
            a, b, c = st.columns(3)
            n = a.text_input("Nama produk")
            h = b.number_input("Harga", 0, step=500)
            s = c.number_input("Stok", 0)
            if st.button("Simpan produk") and n and h:
                D.add_product(n, h, s)
                st.rerun()
        with st.expander("Ubah nama dan harga produk"):
            pid = st.selectbox("Produk", list(nama), format_func=nama.get, key="ubah")
            cur = next(p for p in produk if p["id"] == pid)
            nama_baru = st.text_input("Nama produk", cur["nama"], key=f"enm{pid}")
            harga_baru = st.number_input("Harga", 0, value=int(cur["harga"]), step=500, key=f"eh{pid}")
            if st.button("Simpan perubahan"):
                if not nama_baru.strip():
                    st.error("Nama produk tidak boleh kosong.")
                else:
                    try:
                        D.update_product(pid, nama_baru.strip(), harga_baru)
                    except Exception as e:
                        st.error(str(e))
                    else:
                        st.success("Perubahan disimpan. Perubahan harga tercatat di riwayat.")
                        st.rerun()
    st.subheader("Riwayat perubahan harga")
    if nama:
        pid = st.selectbox("Produk", list(nama), format_func=nama.get, key="riw")
        st.dataframe(pd.DataFrame(D.price_history(pid)), use_container_width=True, hide_index=True)


def page_member():
    ms = D.members()
    st.dataframe(pd.DataFrame([{"Nama": m["nama"], "HP": m.get("hp") or "", "Poin": m["poin"], "Hutang": rp(m["hutang"])} for m in ms]),
                 use_container_width=True, hide_index=True)
    with st.expander("Tambah member"):
        n = st.text_input("Nama")
        h = st.text_input("No. HP")
        if st.button("Simpan member") and n:
            D.add_member(n, h)
            st.rerun()


def page_hutang():
    ada = [m for m in D.members() if m["hutang"] > 0]
    if not ada:
        st.info("Tidak ada hutang berjalan.")
    for m in ada:
        a, b, c = st.columns([3, 2, 1])
        a.write(f"**{m['nama']}**: {rp(m['hutang'])}")
        j = b.number_input("Jumlah dibayar", 0, int(m["hutang"]), step=1000, key=f"j{m['id']}", label_visibility="collapsed")
        if c.button("Catat", key=f"c{m['id']}") and j > 0:
            D.pay_debt(m["id"], j)
            st.rerun()


def page_dash():
    sales = D.sales_today()
    ms = D.members()
    a, b, c, d = st.columns(4)
    a.metric("Omzet hari ini", rp(sum(s["total"] for s in sales)))
    b.metric("Transaksi hari ini", len(sales))
    c.metric("Hutang beredar", rp(sum(m["hutang"] for m in ms)))
    d.metric("Jumlah member", len(ms))
    st.subheader("Omzet 7 hari terakhir")
    st.bar_chart(D.week())
    st.subheader("Transaksi hari ini")
    st.dataframe(pd.DataFrame(sales), use_container_width=True, hide_index=True)


def page_akun():
    m = D.my_member()
    a, b = st.columns(2)
    a.metric("Poin Anda", m["poin"])
    b.metric("Hutang", rp(m["hutang"]))
    st.subheader("Riwayat belanja")
    r = D.my_sales()
    st.dataframe(pd.DataFrame(r), use_container_width=True, hide_index=True) if r else st.caption("Belum ada belanja.")


if me["role"] == "member":
    page_akun()
else:
    nama_tab = ["Kasir", "Produk", "Member", "Hutang"] + (["Dashboard"] if me["role"] == "owner" else [])
    fn = [page_kasir, page_produk, page_member, page_hutang] + ([page_dash] if me["role"] == "owner" else [])
    for t, f in zip(st.tabs(nama_tab), fn):
        with t:
            f()
