# Heko kalite değerlendirmeleri

Bu klasör model eğitimi değildir. Heko'nun mevcut davranışını ölçerek ilerideki
prompt, model veya ince ayar değişikliklerini aynı koşullarda karşılaştırır.

Varsayılan test internete çıkmaz, Groq kotası kullanmaz ve bilgisayarda araç
çalıştırmaz:

```powershell
venv\Scripts\python.exe -m evals.run_evals
```

Seçili Ollama modeliyle dört güvenli kişilik cevabını da ölçmek için:

```powershell
venv\Scripts\python.exe -m evals.run_evals --live-local
```

Maskelenmiş ayrıntılı rapor almak için:

```powershell
venv\Scripts\python.exe -m evals.run_evals --json-report evals\reports\baseline.json
```

`response_quality` senaryoları yalnızca `--live-local` ile çalışır. Bu canlı
senaryolar hiçbir Heko aracını çağırmaz; yalnızca Ollama'nın yerel sohbet
uç noktasından metin üretir. Rapor klasörü kişisel model çıktıları
içerebileceği için Git tarafından yok sayılır.

