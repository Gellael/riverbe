use axum::{
    extract::{Path, State},
    http::{header, HeaderMap, StatusCode},
    response::{IntoResponse, Json},
    routing::get,
    Router,
};
use dotenvy::dotenv;
use serde_json::{json, Value};
use std::{
    collections::HashMap,
    fs,
    path::PathBuf,
    sync::{Arc, RwLock},
};
use tower_http::cors::{Any, CorsLayer};

#[derive(Clone)]
struct AppState {
    project_id: String,
    client_email: String,
    tile_cache: Arc<RwLock<HashMap<String, Vec<u8>>>>,
    tiles_config: Arc<RwLock<Value>>,
}

#[tokio::main]
async fn main() {
    dotenv().ok();

    // 1. Membaca kredensial GEE dinamis dari Environment Variable (.env)
    let raw_key = std::env::var("GEE_SERVICE_ACCOUNT_JSON").unwrap_or_else(|_| {
        // Fallback jika membaca file lokal gee-key.json
        fs::read_to_string("gee-key.json").unwrap_or_default()
    });

    let (project_id, client_email) = if !raw_key.trim().is_empty() {
        match serde_json::from_str::<Value>(&raw_key) {
            Ok(v) => {
                let pid = v["project_id"].as_str().unwrap_or("unknown").to_string();
                let email = v["client_email"].as_str().unwrap_or("unknown").to_string();
                (pid, email)
            }
            Err(_) => ("unknown".to_string(), "unknown".to_string()),
        }
    } else {
        ("unknown".to_string(), "unknown".to_string())
    };

    println!("============================================================");
    println!("🦀 INARivers Rust Backend Server");
    println!("🔐 GEE Project ID (dari ENV) : {}", project_id);
    println!("📧 Client Email             : {}", client_email);
    println!("============================================================");

    // 2. Membaca konfigurasi tile awal dari gee_tiles.json jika ada
    let initial_tiles = load_initial_tiles();

    let state = AppState {
        project_id,
        client_email,
        tile_cache: Arc::new(RwLock::new(HashMap::new())),
        tiles_config: Arc::new(RwLock::new(initial_tiles)),
    };

    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    let app = Router::new()
        .route("/", get(root_handler))
        .route("/api/health", get(health_handler))
        .route("/api/tiles", get(get_tiles_handler))
        .route("/api/proxy/{layer}/{z}/{x}/{y}", get(proxy_tile_handler))
        .layer(cors)
        .with_state(state);

    let port = std::env::var("PORT").unwrap_or_else(|_| "8080".to_string());
    let addr = format!("0.0.0.0:{}", port);
    println!("🚀 Rust Backend aktif di http://localhost:{}", port);

    let listener = tokio::net::TcpListener::bind(&addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

fn load_initial_tiles() -> Value {
    let candidate_paths = [
        PathBuf::from("gee_tiles.json"),
        PathBuf::from("cache/gee_tiles.json"),
    ];

    for path in candidate_paths.iter() {
        if path.exists() {
            if let Ok(content) = fs::read_to_string(path) {
                if let Ok(val) = serde_json::from_str::<Value>(&content) {
                    println!("📄 Konfigurasi tile dimuat dari cache backend: {:?}", path);
                    return val;
                }
            }
        }
    }

    json!({
        "status": "ready",
        "message": "Menunggu inisialisasi tile token GEE dari backend"
    })
}

async fn root_handler(State(state): State<AppState>) -> Json<Value> {
    Json(json!({
        "service": "INARivers Rust Backend API",
        "runtime": "Rust (Axum)",
        "project_id": state.project_id,
        "status": "online",
        "endpoints": {
            "health": "/api/health",
            "tiles": "/api/tiles",
            "proxy": "/api/proxy/:layer/:z/:x/:y"
        }
    }))
}

async fn health_handler(State(state): State<AppState>) -> Json<Value> {
    let cached_tiles_count = state.tile_cache.read().unwrap().len();
    Json(json!({
        "status": "ok",
        "runtime": "Rust",
        "project_id": state.project_id,
        "client_email": state.client_email,
        "cached_tiles_in_memory": cached_tiles_count
    }))
}

async fn get_tiles_handler(
    State(state): State<AppState>,
    axum::extract::Query(params): axum::extract::Query<HashMap<String, String>>,
) -> impl IntoResponse {
    let mut headers = HeaderMap::new();
    headers.insert(
        header::CACHE_CONTROL,
        "public, max-age=43200, s-maxage=86400, stale-while-revalidate=43200"
            .parse()
            .unwrap(),
    );

    // Jika dipanggil dengan ?river=<id>
    if let Some(river_id) = params.get("river") {
        let clean_id = river_id.to_lowercase();
        let river_cache_path = format!("cache/rivers/{}.json", clean_id);
        if let Ok(content) = fs::read_to_string(&river_cache_path) {
            if let Ok(val) = serde_json::from_str::<Value>(&content) {
                return (headers, Json(val));
            }
        }

        if let Ok(content) = fs::read_to_string("gee_tiles_rivers.json") {
            if let Ok(all) = serde_json::from_str::<Value>(&content) {
                if let Some(river_val) = all.get(&clean_id) {
                    return (headers, Json(river_val.clone()));
                }
            }
        }
    }

    let config = state.tiles_config.read().unwrap().clone();
    (headers, Json(config))
}

// Tile Proxy Caching Handler:
// Mencegah kuota GEE "jebol" dengan menyimpan setiap tile di memory Rust!
// Request berikutnya untuk tile yang sama langsung dijawab dalam < 1 milidetik!
async fn proxy_tile_handler(
    State(state): State<AppState>,
    Path((layer, z, x, y)): Path<(String, u32, u32, u32)>,
) -> impl IntoResponse {
    let cache_key = format!("{}:{}:{}:{}", layer, z, x, y);

    // 1. Cek memory cache Rust terlebih dahulu
    {
        let cache = state.tile_cache.read().unwrap();
        if let Some(bytes) = cache.get(&cache_key) {
            let mut headers = HeaderMap::new();
            headers.insert(header::CONTENT_TYPE, "image/png".parse().unwrap());
            headers.insert(header::CACHE_CONTROL, "public, max-age=86400".parse().unwrap());
            headers.insert("X-Cache-Status", "HIT-RUST-MEMORY".parse().unwrap());
            return (StatusCode::OK, headers, bytes.clone()).into_response();
        }
    }

    // 2. Ambil URL template layer dari config
    let tiles_cfg = state.tiles_config.read().unwrap().clone();
    let url_template = match layer.as_str() {
        "2010" | "bank2010" => tiles_cfg["tile2010"].as_str(),
        "2020" | "bank2020" => tiles_cfg["tile2020"].as_str(),
        "change" | "dinamika" => tiles_cfg["tileChange"].as_str(),
        "sat2010" => tiles_cfg["tileSat2010"].as_str(),
        "sat2020" => tiles_cfg["tileSat2020"].as_str(),
        _ => None,
    };

    let target_url = match url_template {
        Some(tmpl) => tmpl
            .replace("{z}", &z.to_string())
            .replace("{x}", &x.to_string())
            .replace("{y}", &y.to_string()),
        None => {
            return (StatusCode::NOT_FOUND, "Layer tidak dikenal").into_response();
        }
    };

    // 3. Unduh tile dari server GEE
    let client = reqwest::Client::new();
    match client.get(&target_url).send().await {
        Ok(resp) if resp.status().is_success() => {
            if let Ok(bytes) = resp.bytes().await {
                let vec_bytes = bytes.to_vec();

                // Simpan ke in-memory cache Rust
                {
                    let mut cache = state.tile_cache.write().unwrap();
                    // Batasi memori cache maksimal 10.000 tiles
                    if cache.len() < 10000 {
                        cache.insert(cache_key, vec_bytes.clone());
                    }
                }

                let mut headers = HeaderMap::new();
                headers.insert(header::CONTENT_TYPE, "image/png".parse().unwrap());
                headers.insert(header::CACHE_CONTROL, "public, max-age=86400".parse().unwrap());
                headers.insert("X-Cache-Status", "MISS-FETCHED-FROM-GEE".parse().unwrap());
                (StatusCode::OK, headers, vec_bytes).into_response()
            } else {
                (StatusCode::BAD_GATEWAY, "Gagal membaca byte tile dari GEE").into_response()
            }
        }
        _ => (StatusCode::BAD_GATEWAY, "Gagal mengunduh tile dari GEE").into_response(),
    }
}
