import base64
import datetime as dt
import html
import io
import json

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Yulfian Store Frozen", page_icon="❄️", layout="wide")

# Ubah ke True untuk mengaktifkan member, poin, dan penjualan hutang.
FITUR_MEMBER = False

rp = lambda n: "Rp" + f"{int(n or 0):,}".replace(",", ".")
ROLES = {"owner": "Pemilik", "kasir": "Kasir", "member": "Member"}

try:
    LIVE = "supabase" in st.secrets  # tanpa secrets -> mode pratinjau
except Exception:
    LIVE = False


# ---------------------------------------------------------------- gambar
def to_data_url(file):
    """Perkecil gambar ke maks. 300 px lalu simpan sebagai teks (data URL)."""
    from PIL import Image
    im = Image.open(file).convert("RGB")
    im.thumbnail((300, 300))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def foto(p):
    if p.get("gambar"):
        st.image(base64.b64decode(p["gambar"].split(",", 1)[1]), use_container_width=True)
    else:
        st.markdown(f"<div style='font-size:52px;text-align:center;background:#e3f1f7;border-radius:8px;padding:10px'>{p.get('e', '❄️')}</div>",
                    unsafe_allow_html=True)


# ---------------------------------------------------------------- data: pratinjau
class Demo:
    """Data contoh di memori sesi. Hilang saat sesi berakhir."""

    def __init__(self):
        ss = st.session_state
        if "demo" not in ss:
            ss.demo = {
                "p": [
                    {"id": 1, "e": "🍗", "nama": "Nugget ayam 500 g", "harga": 38000, "stok": 24, "sold": 31, "gambar": None, "h": [35000, 38000]},
                    {"id": 2, "e": "🌭", "nama": "Sosis sapi 1 kg", "harga": 62000, "stok": 15, "sold": 18, "gambar": None, "h": [62000]},
                    {"id": 3, "e": "🍢", "nama": "Bakso sapi 500 g", "harga": 35000, "stok": 30, "sold": 44, "gambar": None, "h": [32000, 35000]},
                    {"id": 4, "e": "🍟", "nama": "Kentang goreng 1 kg", "harga": 45000, "stok": 18, "sold": 22, "gambar": None, "h": [45000]},
                    {"id": 5, "e": "🥟", "nama": "Dimsum ayam isi 10", "harga": 28000, "stok": 22, "sold": 39, "gambar": None, "h": [25000, 28000]},
                    {"id": 6, "e": "🦐", "nama": "Udang kupas 500 g", "harga": 70000, "stok": 6, "sold": 12, "gambar": None, "h": [75000, 70000]},
                ],
                "m": [
                    {"id": 1, "nama": "Bu Sari", "hp": "0812-3456-7890", "poin": 42, "hutang": 85000},
                    {"id": 2, "nama": "Pak Andi", "hp": "0857-1122-3344", "poin": 17, "hutang": 0},
                ],
                "s": [{"t": "08:12", "m": "Umum", "total": 112000, "metode": "tunai"},
                      {"t": "09:40", "m": "Umum", "total": 38000, "metode": "tunai"}],
                "n": 100,
            }
        self.d = ss.demo

    def _id(self):
        self.d["n"] += 1
        return self.d["n"]

    def products(self):
        return self.d["p"]

    def add_product(self, nama, harga, stok, gambar=None):
        self.d["p"].append({"id": self._id(), "e": "❄️", "nama": nama, "harga": harga, "stok": stok,
                            "sold": 0, "gambar": gambar, "h": [harga]})

    def update_product(self, pid, nama, harga, stok, gambar=None):
        p = next(x for x in self.d["p"] if x["id"] == pid)
        p["nama"], p["stok"] = nama, stok
        if gambar:
            p["gambar"] = gambar
        if harga != p["harga"]:
            p["harga"] = harga
            p["h"].append(harga)

    def deactivate(self, pid):
        self.d["p"] = [x for x in self.d["p"] if x["id"] != pid]

    def price_history(self, pid):
        h = next(x for x in self.d["p"] if x["id"] == pid)["h"]
        return [{"Perubahan": "Harga awal" if i == 0 else f"Ke-{i}",
                 "Harga lama": rp(h[i - 1]) if i else "-", "Harga baru": rp(v)} for i, v in enumerate(h)][::-1]

    def top_products(self):
        return sorted(([p["nama"], p["sold"]] for p in self.d["p"]), key=lambda x: -x[1])[:5]

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
            byid[i["product_id"]]["sold"] += i["qty"]
        self.d["s"].insert(0, {"t": dt.datetime.now().strftime("%H:%M"), "m": m["nama"] if m else "Umum",
                               "total": total, "metode": metode})
        return {"total": total, "poin": poin}

    def pay_debt(self, mid, jumlah):
        m = next(x for x in self.d["m"] if x["id"] == mid)
        m["hutang"] = max(0, m["hutang"] - jumlah)

    def sales_today(self):
        return [{"waktu": s["t"], "member": s["m"], "total": s["total"], "metode": s["metode"]} for s in self.d["s"]]

    def week(self):
        hari = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Hari ini"]
        data = [820000, 640000, 910000, 760000, 1020000, 880000, sum(s["total"] for s in self.d["s"])]
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

    def add_product(self, nama, harga, stok, gambar=None):
        self.c.table("products").insert({"nama": nama, "harga": harga, "stok": stok, "gambar": gambar}).execute()

    def update_product(self, pid, nama, harga, stok, gambar=None):
        data = {"nama": nama, "harga": harga, "stok": stok}
        if gambar:
            data["gambar"] = gambar
        self.c.table("products").update(data).eq("id", pid).execute()

    def deactivate(self, pid):
        self.c.table("products").update({"aktif": False}).eq("id", pid).execute()

    def price_history(self, pid):
        r = self.c.table("price_history").select("*").eq("product_id", pid).order("dibuat", desc=True).execute().data
        return [{"Waktu": x["dibuat"][:16].replace("T", " "),
                 "Harga lama": rp(x["harga_lama"]) if x["harga_lama"] is not None else "-",
                 "Harga baru": rp(x["harga_baru"])} for x in r]

    def top_products(self):
        r = self.c.table("sale_items").select("nama,qty").limit(2000).execute().data
        if not r:
            return []
        df = pd.DataFrame(r).groupby("nama")["qty"].sum().sort_values(ascending=False).head(5)
        return [[n, int(q)] for n, q in df.items()]

    def members(self):
        return self.c.table("members").select("*").order("nama").execute().data

    def my_member(self):
        return self.c.table("members").select("*").eq("user_id", st.session_state.me["id"]).single().execute().data

    def add_member(self, nama, hp):
        self.c.table("members").insert({"nama": nama, "hp": hp}).execute()

    def checkout(self, mid, items, bayar, metode):
        r = self.c.rpc("checkout", {"p_member": mid, "p_items": items, "p_bayar": bayar, "p_metode": metode}).execute().data
        harga = {p["id"]: p["harga"] for p in self.products()}
        return {"total": sum(harga[i["product_id"]] * i["qty"] for i in items), "poin": r["poin"]}

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
    st.caption("Masuk untuk memakai kasir. Akun pertama yang terdaftar otomatis menjadi pemilik.")
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
    if b.button("Daftar akun baru"):
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
    peran = st.sidebar.selectbox("Lihat sebagai", ["owner", "kasir"], format_func=ROLES.get)
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
            with cols[i % 3].container(border=True):
                foto(p)
                st.markdown(f"**{p['nama']}**  \n{rp(p['harga'])} · stok {p['stok']}")
                if st.button("Tambah", key=f"p{p['id']}", use_container_width=True, disabled=p["stok"] <= ss.cart.get(p["id"], 0)):
                    ss.cart[p["id"]] = ss.cart.get(p["id"], 0) + 1
                    st.rerun()
    with kanan:
        st.subheader("Keranjang")
        if not ss.cart:
            st.caption("Klik Tambah pada produk untuk mengisi keranjang.")
        for pid in list(ss.cart):
            p = byid[pid]
            ss.cart[pid] = st.number_input(f"{p['nama']} ({rp(p['harga'])})", 0, int(p["stok"]), ss.cart[pid], key=f"q{pid}")
            if ss.cart[pid] == 0:
                del ss.cart[pid]
                st.rerun()
        total = sum(byid[i]["harga"] * n for i, n in ss.cart.items())
        st.metric("Total", rp(total))
        mid, metode, opsi = None, "tunai", {None: "Tanpa member"}
        if FITUR_MEMBER:
            opsi.update({m["id"]: f"{m['nama']} · {m['poin']} poin" for m in D.members()})
            mid = st.selectbox("Member", list(opsi), format_func=opsi.get)
            metode = st.radio("Pembayaran", ["tunai", "hutang"], horizontal=True)
            if mid:
                st.caption(f"Poin didapat transaksi ini: {total // 10000}")
        bayar = st.number_input("Uang diterima", 0, value=int(total), step=1000) if metode == "tunai" else 0
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
    nama = {p["id"]: p["nama"] for p in produk}

    cols = st.columns(4)
    for i, p in enumerate(produk):
        with cols[i % 4].container(border=True):
            foto(p)
            st.markdown(f"**{p['nama']}**  \n{rp(p['harga'])} · stok {p['stok']}")

    if own:
        st.subheader("Kelola produk")
        pilih = st.selectbox("Pilih produk", ["__baru__"] + list(nama),
                             format_func=lambda x: "➕ Produk baru" if x == "__baru__" else nama[x], key="kelola")
        cur = {"nama": "", "harga": 0, "stok": 0} if pilih == "__baru__" else next(p for p in produk if p["id"] == pilih)
        with st.form(f"form_{pilih}"):
            n = st.text_input("Nama produk", cur["nama"])
            h = st.number_input("Harga", 0, value=int(cur["harga"]), step=500)
            s = st.number_input("Stok", 0, value=int(cur["stok"]))
            f = st.file_uploader("Gambar produk (kosongkan jika tidak diganti)", type=["png", "jpg", "jpeg", "webp"])
            kirim = st.form_submit_button("Simpan", type="primary")
        if kirim:
            if not n.strip() or h <= 0:
                st.error("Isi nama dan harga produk.")
            else:
                try:
                    g = to_data_url(f) if f else None
                    if pilih == "__baru__":
                        D.add_product(n.strip(), h, s, g)
                    else:
                        D.update_product(pilih, n.strip(), h, s, g)
                except Exception as e:
                    st.error(str(e))
                else:
                    st.success("Produk disimpan. Perubahan harga tercatat di riwayat.")
                    st.rerun()
        if pilih != "__baru__":
            ya = st.checkbox("Saya yakin ingin menghapus produk ini dari daftar", key=f"y{pilih}")
            if st.button("Hapus produk", disabled=not ya):
                D.deactivate(pilih)
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
    total = sum(s["total"] for s in sales)
    low = [p for p in D.products() if p["stok"] <= 10]
    a, b, c, d = st.columns(4)
    a.metric("Omzet hari ini", rp(total))
    b.metric("Transaksi hari ini", len(sales))
    c.metric("Rata-rata per transaksi", rp(total / len(sales)) if sales else rp(0))
    d.metric("Stok menipis", f"{len(low)} produk")
    if FITUR_MEMBER:
        ms = D.members()
        st.metric("Hutang beredar", rp(sum(m["hutang"] for m in ms)))
    st.subheader("Omzet 7 hari terakhir")
    st.bar_chart(D.week())
    k, l = st.columns(2)
    with k:
        st.subheader("Produk terlaris")
        st.dataframe(pd.DataFrame(D.top_products(), columns=["Produk", "Terjual"]), use_container_width=True, hide_index=True)
    with l:
        st.subheader("Stok menipis")
        if low:
            st.dataframe(pd.DataFrame([{"Produk": p["nama"], "Sisa": p["stok"]} for p in low]), use_container_width=True, hide_index=True)
        else:
            st.caption("Semua stok aman.")
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
    if FITUR_MEMBER:
        page_akun()
    else:
        st.info("Akun ini belum punya akses ke kasir. Minta pemilik toko mengubah peran akun Anda menjadi kasir.")
else:
    nama_tab = ["Kasir", "Produk"]
    fn = [page_kasir, page_produk]
    if FITUR_MEMBER:
        nama_tab += ["Member", "Hutang"]
        fn += [page_member, page_hutang]
    if me["role"] == "owner":
        nama_tab.append("Dashboard")
        fn.append(page_dash)
    for t, f in zip(st.tabs(nama_tab), fn):
        with t:
            f()
