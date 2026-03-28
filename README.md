# LawBridge Backend

Bu klasor artik sadece backend servisini icerir. Frontend'i ayri bir klasorden calistirip bu API'ye baglayabilirsin.

## Stack

- FastAPI
- Sentence Transformers
- PyTorch
- SQLite

## Model mantigi

Gonderdigin MiniLM paketi dogrudan bir sentiment classifier degil; bir `SentenceTransformer` encoder modeli. Backend bu modeli embedding uretmek icin kullaniyor ve gelen yorumu olumlu, notr ve olumsuz prototip cumlelerle karsilastirarak sentiment tahmini yapiyor.

## Kurulum

1. Ornek ortam dosyasini kopyala:

```powershell
Copy-Item .env.example .env
```

2. Model zip dosyasini `models/` altina ac:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_model.ps1 -ZipPath "C:\Users\yunus\Downloads\Emsal Arama MiniLM Modeli_seed42_ep7zip.zip"
```

3. Bagimliliklari kur:

```powershell
pip install -r requirements.txt
```

4. API'yi baslat:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Frontend baglantisi

Ayri klasordeki frontend tarafinda API taban adresini su sekilde ayarla:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Frontend farkli bir origin'den aciliyorsa `.env` icindeki `LAWBRIDGE_CORS_ORIGINS` degerine onu ekle.

## Endpointler

- `GET /`
- `GET /docs`
- `GET /api/v1/analysis/health`
- `POST /api/v1/analysis/sentiment`
- `GET /api/v1/analysis/history`

## Ornek istek

```json
{
  "text": "Hizmet hizliydi ve sonuc oldukca faydali oldu."
}
```
