# Heko Geliştirme Yol Haritası

## Bu turda tamamlananlar

- Kullanıcı tarafından yönetilebilir sabah ve akşam özeti
- Çevrimdışı görev, not, hava, hafıza ve listeleme komutları
- Not, görev, hava ve dosya isteklerinde çok adımlı eksik bilgi tamamlama
- Her biri ayrı geçmişe ve ayrı çalışan iş parçacığına sahip çoklu sohbet pencereleri
- Pencereler arasında ortak kişisel hafıza, görev, not ve hatırlatıcı servisleri
- Pencerelerin sonuçlarını paylaşan kalıcı `SharedWorkspace`
- Diğer sohbet çalışmalarını komutla veya Kontrol Merkezi'nden görüntüleme
- Küçük metin/kod dosyalarını hassas dosya ve boyut korumasıyla salt okunur inceleme
- Groq kullanılamadığında isteğe bağlı Ollama yerel model geri dönüşü
- Karakterin işlem, uyarı ve bekleme durumları

## Çoklu sohbet davranışı

- Üst çubuktaki `+` düğmesi yeni ve bağımsız bir sohbet açar.
- Bir penceredeki uzun yanıt diğer pencerelerde yazışmayı kilitlemez.
- Konuşma geçmişleri `memory/sessions/` altında ayrı tutulur.
- Üretilen yanıtlar ve incelenen dosyalar ortak çalışma deposuna kaydedilir.
- `diğer pencerede ne oldu` komutu diğer oturumların son çıktılarını getirir.
- Kontrol Merkezi > Çalışmalar sekmesi ortak sonuçları listeler.
- Model, diğer oturumların bütün geçmişi yerine sınırlı son çalışma özetini bağlama alır.

## İsteğe bağlı yerel model

Ollama kuruluysa `.env` içine örneğin aşağıdakiler eklenebilir:

```env
OLLAMA_MODEL=qwen3:8b
OLLAMA_URL=http://127.0.0.1:11434
```

Yerel model tanımlı değilse mevcut Groq davranışı korunur. Yerel araç komutları
model kurulmasa da çalışır.

## Kalan sağlamlaştırma işleri

1. Aynı dosyayı iki sohbetin eşzamanlı değiştirmesine karşı yazma kilitleri
2. Çalışan uzun işlerin iptal/duraklatma ve ayrıntılı ilerleme kayıtları
3. PDF ve Word içerik okuyucuları
4. Kullanıcı izinli ekran görüntüsü farkındalığı
5. Ollama model seçimi ve bağlantı testinin Ayarlar ekranına eklenmesi
6. Daha kapsamlı karakter animasyonları

Bu maddeler dış uygulama kurulumu, yeni dosya yazma yetkileri veya görsel algı
akışı gerektirdiği için temel mimariden ayrı sağlamlaştırma aşamasında ele alınır.
