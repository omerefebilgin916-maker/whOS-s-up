# whOS's up?

> System Status Monitor: "Bilgisayarım şu anda ne durumda ve ne yapıyor?"

Terminalde `whosup` yazın; CPU, RAM, GPU, disk, ağ, güç durumu ve en çok kaynak kullanan süreçler tek ekranda görünsün. Tamamen yerel çalışır ve gizlilik varsayılandır.

**Sürüm:** 0.1.1 · **Öncelikli platform:** Linux · **Lisans:** MIT

## Kurulum

Gereksinimler: Python 3.9+, `psutil`, `rich` (başka bağımlılık yok).

```bash
cd whosup
./install.sh
```

Kurulumdan sonra `whosup` komutu doğrudan kullanılabilir; sanal ortamı her terminalde yeniden etkinleştirmeniz gerekmez. Kurulum yerel olarak `${XDG_DATA_HOME:-~/.local/share}/whosup` altında tutulur ve `~/.local/bin/whosup` bağlantısı oluşturulur.

Geliştirme/test için sanal ortam kullanmak isterseniz:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
```

Kurmadan denemek için: `python -m whosup`.

## Komutlar

| Komut | Açıklama |
| --- | --- |
| `whosup` | Anlık sistem durumunu gösterir |
| `whosup watch` | Canlı monitör (1 sn aralık, `Ctrl+C` ile çıkış) |
| `whosup watch --interval 2` | Canlı ekranı 2 saniyede bir yeniler (en az 0.2) |
| `whosup version` | Sürüm ve ürün adı |
| `whosup --version` | Yalnızca `whOS's up? 0.1.1` |
| `whosup export --md` | Markdown snapshot (`whosup-YYYY-MM-DD-HHMMSS.md`) |
| `whosup export --txt` | TXT snapshot |
| `whosup export --md --output system.md` | Belirtilen dosyaya yazar |
| `whosup export --txt --output system.txt` | Belirtilen dosyaya yazar |
| `whosup --help` | Yardım |

`whosup` ve `whosup export` aynı veri toplama kodunu kullanır. Export, sürekli güncellenen bir log değil, **tek bir anlık snapshot**'tır.

## Örnek çıktı

Aşağıdaki, `whosup export --txt` komutunun bir Linux makinesinde üretebileceği örnek çıktıdır (ekran görünümü aynı bölümleri renkli gösterir):

```text
whOS's up? — System Snapshot
Date: 2026-09-30 21:19:15

SYSTEM
------
CPU:            0%
Cores:          1 physical / 1 logical
RAM:            6%
RAM used:       243 MB / 3.91 GB
RAM free:       3.67 GB
GPU:            Unavailable
Processes: 48

STORAGE
-------
Disk (/): 252 GB
Used:     8.55 GB  (46.1%)
Free:     9.98 GB

NETWORK
-------
Download: 0 B/s
Upload:   0 B/s

POWER
-----
Not available

TOP PROCESSES
-------------
Process               RAM  CPU
rclone-filestore  41.2 MB   0%
python3           16.2 MB   2%
process_api       4.82 MB   0%
sh                1.84 MB   0%
kthreadd              0 B   0%

DOWNLOADS
---------
No active supported download tools detected

POSSIBLY UNEXPECTED
-------------------
None detected

whOS's up? v0.1.1
```

## Privacy

whOS's up? "bilgisayarım hakkında ihtiyacım olan bilgiyi göster; benim veya başkalarının kişisel bilgilerini gereksiz yere toplama" ilkesiyle tasarlanmıştır.

- **Telemetry göndermez.** Analytics, crash report, kullanım istatistiği, uzaktan loglama ve otomatik güncelleme kontrolü yoktur.
- **Ağ bağlantısı kurmaz.** Kodda `socket`, `urllib`, `http`, `requests` gibi ağ modülleri yoktur; sistem raporunuzu hiçbir sunucuya veya servise göndermez. Ağ hızı yalnızca işletim sisteminin yerel sayaçlarından okunur.
- **Kişisel verileri varsayılan olarak toplamaz:** kullanıcı adı, hostname, IP/MAC adresi, seri numarası, machine-id, ortam değişkenleri, `PATH`, shell geçmişi, dosya yolları, anahtarlar ve parolalar toplanmaz ve gösterilmez.
- **Process görünümü yalnızca mevcut kullanıcıya aittir.** Diğer kullanıcıların süreçleri listelenmez ve sayılmaz. Süreç sahibi yalnızca filtrelemek için kontrol edilir, saklanmaz, gösterilmez. Command line, çalışma dizini, ortam değişkenleri ve açık dosyalar hiç okunmaz. (`--all-users` bu sürümde yoktur; mimari ileride buna izin verecek şekilde hazırdır ve asla varsayılan olmayacaktır.)
- **Export kişisel bilgi içermez.** Her değer `PUBLIC` veya `PRIVATE` olarak sınıflandırılır. Export yalnızca açıkça `PUBLIC` işaretlenenleri yazar; yeni eklenen bir alan varsayılan olarak `PRIVATE` olduğundan yanlışlıkla export'a sızmaz. Dosya adı yalnızca tarih/saat içerir; yeni dosyalar yalnızca sahibin okuyabileceği izinle (`0600`) oluşturulur. `--output` yolu tamamen sizin kontrolünüzdedir.
- **Browser geçmişi, cookie ve credential okunmaz. Dosya içerikleri okunmaz.** Dosya sistemi taranmaz, home dizini gezilmez.
- **Hata mesajları temizdir.** Traceback gösterilmez; mesajlarda kullanıcı adı, home yolu veya dosya yolu yer almaz.

| Sınıf | Örnekler |
| --- | --- |
| PUBLIC (export'a girer) | CPU/RAM/disk kullanımı, GPU kullanım yüzdesi, ağ hızı, batarya yüzdesi, süreç adları ve kaynak kullanımı, indirme durumu/yüzdesi/hızı |
| PRIVATE (yalnızca ekranda veya hiç yok) | GPU model adı, indirilen dosya adı; ayrıca kullanıcı adı, hostname, IP, MAC, seri no, dosya yolları, command line, ortam değişkenleri, kimlik bilgileri (bunlar zaten toplanmaz) |

Bu garantiler `tests/` altındaki testlerle doğrulanır; örneğin kaynak kodda ağ/telemetry modülü, kimlik toplayan API'ler veya indirme sağlayıcılarında dosya tarama/tarayıcı verisi erişimi bulunursa test başarısız olur.

> Not: Bu testler sözleşmeyi korur ama her şeyi kanıtlamaz. Süreç adları kullanıcı tarafından belirlenebilir; bir programın adı kişisel bir ifade içeriyorsa export'ta görünür. Export'u paylaşmadan önce göz atmanız önerilir.

## Veri nasıl toplanıyor?

- **CPU / RAM:** `psutil`. RAM "used" = toplam − kullanılabilir; "free" kullanılabilir bellektir.
- **Storage:** Dosya sistemi kökü (Linux'ta `/`). SSD/HDD ayrımı yapılmaz, tahmin edilmez. Kök olmayan bir yol etiket olarak gösterilmez.
- **Network:** İki ölçüm arasındaki sayaç farkı ÷ geçen süre. Loopback hariçtir; arayüz adı, IP veya MAC okunmaz.
- **Power:** Batarya yoksa `Not available`. Linux'ta şarj durumu `/sys/class/power_supply` üzerinden okunur.
- **GPU:** `nvidia-smi` (yalnızca model adı ve kullanım değerleri istenir; seri no/UUID istenmez) veya `amdgpu` sysfs. Bulunamazsa `Unavailable`. Model adı yalnızca ekranda görünür.
- **Top processes:** Yalnızca sizin süreçleriniz. Aynı adlı süreçler toplanır (ör. `firefox (x12)`), RAM'e (RSS) göre sıralanır. CPU yüzdesi **tüm makineye göre** normalize edilir (0–100).

## Downloads

İndirme tespiti yalnızca güvenli, açıkça tanımlı **sağlayıcılar** üzerinden yapılır (`DownloadProvider.detect() → DownloadItem`).

- **Dahili sağlayıcı:** Sizin kullanıcınız altında çalışan `wget`, `curl`, `aria2c`, `axel`, `yt-dlp`, `youtube-dl` süreçlerini yalnızca **süreç adıyla** tespit eder. İlerleme ve hız bilinmediğinden gösterilmez; durum "Download tool running" olarak yazılır ("indiriyor" iddiası yoktur).
- **Desteklenmeyenler:** Tarayıcı ve Steam indirmeleri. Bunlar tarayıcı profilini, veritabanını veya uygulama dosyalarını okumayı gerektirir; gizlilik nedeniyle bilerek yapılmaz. Mesaj: `No active supported download tools detected`.
- Hiç sağlayıcı kayıtlı değilse: `No supported download sources detected`.
- **Dosya adları:** Bir sağlayıcı dosya adı verirse ekranda yalnızca son bileşen gösterilir (yol atılır); export'ta ise anonim kalır: `Firefox  Active download  74%  12.4 MB/s`.

Yeni sağlayıcı yazarken: dosya sistemi taramayın, tarayıcı/credential verisine dokunmayın, bir dosya okumanız gerekiyorsa önce `privacy.assert_not_sensitive(path)` çağırın.

## Possibly Unexpected

Bu bölüm bir güvenlik ürünü **değildir**. Hiçbir süreç "virüs, malware, zararlı, tehlikeli" diye etiketlenmez; yalnızca "daha yakından bakılabilir" denir. İlk kurallar bilinçli olarak çok muhafazakârdır (yanlış pozitif yerine hiçbir şey işaretlememek tercih edilir):

- **Recently started and using a lot of CPU:** Son 2 dakikada başlamış ve **tüm makinenin** CPU'sunun %80'inden fazlasını kullanan süreç.
- **High CPU usage for over a minute:** `watch` modunda, tüm makinenin %80'inden fazlasını 1 dakikadan uzun süre kesintisiz kullanan süreç. Tek seferlik `whosup` bunu ölçemez, dolayısıyla bu kural orada tetiklenmez.

CPU'su %20 olan bir süreç asla işaretlenmez. Yüksek CPU tek başına kötü amaçlı yazılım anlamına gelmez (derleme, video işleme vb.). Süreç başına ağ hızı `psutil` ile ölçülemediği için ağ kuralı yoktur.

Kurallar `Rule → Finding | None` şeklindedir ve yalnızca `ProcessObservation` alır (ad, CPU, RAM, yaklaşık yaş). Kullanıcı adı, command line, cwd, ortam değişkeni veya dosya yolu kurallara hiç verilmez, `Finding` içinde de tutulmaz.

## v0.1.1 değişiklikleri

- Process sayacı artık ekranda `Processes` olarak gösterilir. Başka kullanıcıların süreçleri varsayılan olarak yine gizlidir.
- Disk bölümü `Total / Used / Free` biçimine çevrildi; kullanım yüzdesi `Used` satırında açıkça gösterilir.
- İndirme sağlayıcısı yalnızca desteklenen komut satırı indirme araçlarını yerel süreç adlarından algılar; browser/Steam profilleri okunmaz.
- `POSSIBLY UNEXPECTED` kuralları muhafazakâr kalır; kesin güvenlik/zararlı yazılım sonucu üretmez.
- Gizlilik ve export sınırları korunur; yeni alanlar varsayılan olarak export edilmez.

## Proje yapısı

```text
whosup/
├── whosup/
│   ├── __init__.py     tek sürüm kaynağı
│   ├── __main__.py     python -m whosup
│   ├── cli.py          argparse komutları
│   ├── privacy.py      Visibility (PUBLIC/PRIVATE), hassas yol koruması, güvenli hata mesajları
│   ├── system.py       CPU/RAM + Snapshot + SnapshotCollector
│   ├── processes.py    süreçler (yalnızca mevcut kullanıcı) + kurallar
│   ├── network.py      ağ hızı
│   ├── power.py        batarya / AC
│   ├── storage.py      disk
│   ├── gpu.py          GPU sağlayıcıları (PROVIDERS)
│   ├── downloads.py    indirme sağlayıcıları (PROVIDERS)
│   ├── formatting.py   Snapshot → bölümler, public_sections()
│   ├── export.py       Markdown / TXT (yalnızca PUBLIC)
│   └── ui.py           rich arayüzü ve watch modu
├── tests/
├── pyproject.toml
├── README.md
└── LICENSE
```

## Genişletme noktaları

- **GPU sağlayıcısı:** `gpu.py` içinde `GpuInfo | None` döndüren fonksiyonu `PROVIDERS` listesine ekleyin.
- **İndirme sağlayıcısı:** `label` ve `detect()` olan sınıfı `downloads.PROVIDERS` listesine ekleyin (yukarıdaki gizlilik kurallarına uyarak).
- **Possibly unexpected kuralı:** `ProcessObservation` alıp `Finding | None` döndüren fonksiyonu `processes.RULES` listesine ekleyin.
- **Yeni bir değer göstermek:** `formatting.py` içinde `Row` eklerken export'a girmesini istiyorsanız açıkça `PUBLIC` işaretleyin; aksi halde yalnızca ekranda kalır.
- **Windows:** Platforma bağlı kod sağlayıcılarda toplandı; süreç sahibi kontrolü Windows'ta kullanıcı kimliği karşılaştırmasıyla yapılır (yalnızca karşılaştırma, hiçbir yerde gösterilmez). Windows henüz test edilmedi.

## Testler

```bash
pytest          # veya: python -m unittest discover -s tests -t .
```

## Sürümleme

Semantic Versioning. Sürüm yalnızca `whosup/__init__.py` içinde tanımlıdır; `pyproject.toml`, `whosup --version` ve `whosup version` buradan okur.
