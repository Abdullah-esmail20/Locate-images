from flask import Flask, render_template, request, url_for
import exifread
import folium
import os
from geopy.geocoders import Nominatim

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
STATIC_FOLDER = 'static'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Upload ve statik klasörlerin varlığını kontrol et
for folder in [UPLOAD_FOLDER, STATIC_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

geolocator = Nominatim(user_agent="geo_locator_app")

def get_decimal_from_dms(dms, ref):
    """DMS formatından decimal formatına çevir"""
    try:
        degrees = dms[0].num / dms[0].den
        minutes = dms[1].num / dms[1].den
        seconds = dms[2].num / dms[2].den
        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
        if ref in ['S', 'W']:
            decimal = -decimal
        return decimal
    except (ZeroDivisionError, AttributeError, IndexError):
        return None

def get_exif_location_and_info(image_path):
    """Fotoğraftan GPS ve zaman bilgilerini çıkar"""
    try:
        with open(image_path, 'rb') as f:
            tags = exifread.process_file(f)
            
            # GPS bilgilerini al
            lat = tags.get('GPS GPSLatitude')
            lat_ref = tags.get('GPS GPSLatitudeRef')
            lon = tags.get('GPS GPSLongitude')
            lon_ref = tags.get('GPS GPSLongitudeRef')
            
            # Zaman bilgisini al
            datetime = tags.get('EXIF DateTimeOriginal') or tags.get('Image DateTime')
            
            if lat and lon and lat_ref and lon_ref:
                lat_decimal = get_decimal_from_dms(lat.values, lat_ref.values)
                lon_decimal = get_decimal_from_dms(lon.values, lon_ref.values)
                
                if lat_decimal is not None and lon_decimal is not None:
                    return lat_decimal, lon_decimal, str(datetime) if datetime else None
                    
    except Exception as e:
        print(f"EXIF okuma hatası: {e}")
        
    return None, None, None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Dosya kontrolü
        if 'photo' not in request.files:
            return render_template('index.html', error="Dosya yüklenmedi.")
            
        file = request.files['photo']
        
        if file.filename == '':
            return render_template('index.html', error="Lütfen önce bir fotoğraf seçiniz.")
        
        # Dosya uzantısı kontrolü
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff'}
        if not ('.' in file.filename and 
                file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
            return render_template('index.html', error="Geçerli bir fotoğraf formatı seçiniz (JPG, PNG, GIF, vb.).")
        
        # Dosyayı kaydet
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        try:
            file.save(filepath)
        except Exception as e:
            return render_template('index.html', error="Dosya kaydedilirken hata oluştu.")
        
        # GPS bilgilerini çıkar
        lat, lon, datetime = get_exif_location_and_info(filepath)
        
        if lat is not None and lon is not None:
            try:
                # Konum bilgilerini al
                location = geolocator.reverse((lat, lon), language='tr')
                address = location.raw.get('address', {}) if location else {}
                
                # Şehir bilgisi
                city = (address.get('city') or 
                       address.get('town') or 
                       address.get('village') or 
                       address.get('municipality') or 
                       "Bilinmiyor")
                
                # Ülke bilgisi
                country = address.get('country', "Bilinmiyor")
                
                # Sokak bilgisi - birden fazla alanı kontrol et
                street = (address.get('road') or 
                         address.get('pedestrian') or 
                         address.get('street') or 
                         address.get('footway') or 
                         address.get('path') or 
                         "Bilinmiyor")
                
                # Harita oluştur
                map_obj = folium.Map(
                    location=[lat, lon], 
                    zoom_start=15,
                    tiles='OpenStreetMap'
                )
                
                # Marker ekle
                tooltip_text = f"📍 Fotoğraf konumu: {street}, {city}, {country}"
                popup_text = f"""
                <div style="text-align: center; font-family: Arial;">
                    <h4>📸 Fotoğraf Konumu</h4>
                    <p><strong>🛣️ Sokak:</strong> {street}</p>
                    <p><strong>🏙️ Şehir:</strong> {city}</p>
                    <p><strong>🌍 Ülke:</strong> {country}</p>
                    <p><strong>📍 Koordinatlar:</strong><br>{lat:.6f}, {lon:.6f}</p>
                </div>
                """
                
                folium.Marker(
                    [lat, lon], 
                    tooltip=tooltip_text,
                    popup=folium.Popup(popup_text, max_width=300),
                    icon=folium.Icon(color='red', icon='camera', prefix='fa')
                ).add_to(map_obj)
                
                # Haritayı static klasörüne kaydet
                map_path = os.path.join(STATIC_FOLDER, 'map.html')
                map_obj.save(map_path)
                
                # Yüklenen dosyayı temizle (isteğe bağlı)
                try:
                    os.remove(filepath)
                except:
                    pass
                
                return render_template('map.html', 
                                     street=street,
                                     city=city, 
                                     country=country, 
                                     datetime=datetime)
                                     
            except Exception as e:
                return render_template('index.html', 
                                     error="Konum bilgileri alınırken hata oluştu. Lütfen internet bağlantınızı kontrol edin.")
        else:
            # Yüklenen dosyayı temizle
            try:
                os.remove(filepath)
            except:
                pass
            return render_template('index.html', 
                                 error="Bu fotoğraf GPS verisi içermiyor. Lütfen GPS özelliği açık olan bir cihazla çekilmiş fotoğraf seçiniz.")
    
    return render_template('index.html')

@app.errorhandler(404)
def not_found(error):
    return render_template('index.html', error="Sayfa bulunamadı."), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('index.html', error="Sunucu hatası oluştu."), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)