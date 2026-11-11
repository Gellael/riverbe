# INARivers Backend (Rust + Axum)

Backend API berkecepatan tinggi yang dibangun menggunakan **Rust (Axum)** untuk melayani layer WebGIS Google Earth Engine (GEE).

## Fitur Utama
1. **Keamanan Kredensial (.env)**: Kredensial Service Account GEE disimpan secara aman di variabel lingkungan (`GEE_SERVICE_ACCOUNT_JSON`), tanpa hardcode project ID di kode program.
2. **Tile Caching Proxy**: Menyediakan endpoint `/api/proxy/{layer}/{z}/{x}/{y}` yang menyimpan tile di memori Rust untuk mencegah kuota GEE terkuras.
3. **Penyajian Cepat**: Endpoint `/api/tiles` menyajikan konfigurasi URL tile layer dengan header caching HTTP 24 jam.

## Cara Menjalankan Lokal

```bash
# Di dalam folder backend
cargo run
```
Server akan aktif di `http://localhost:8080`.

## Endpoints
- `GET /api/health` : Status kesehatan server dan project ID GEE aktif.
- `GET /api/tiles` : Mengembalikan URL template tile XYZ untuk seluruh layer.
- `GET /api/proxy/{layer}/{z}/{x}/{y}` : Proxy tile ber-cache (layer: `2010`, `2020`, `change`, `sat2010`, `sat2020`).

## Deployment
- **Backend (Vercel)**:
  Tambahkan variabel lingkungan di Vercel Dashboard:
  - `GEE_SERVICE_ACCOUNT_JSON`: Isi string JSON dari Service Account GEE Anda.
  - `PORT`: `8080` (opsional)
- **Frontend (Cloudflare Pages)**:
  Tambahkan variabel lingkungan di Cloudflare Pages:
  - `VITE_API_URL`: URL backend Vercel Anda (misal `https://backend-anda.vercel.app`).

