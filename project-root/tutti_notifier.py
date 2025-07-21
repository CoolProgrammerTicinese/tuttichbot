import asyncio
import json
import os
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import telegram
import time

# --- CONFIGURAZIONE ---
TELEGRAM_BOT_TOKEN = "7587826439:AAEGMTESvSa00C9pERTRgLTAWDZTlZO0Y-0"
TELEGRAM_CHAT_ID = "254508283"
TARGET_URL = "https://www.tutti.ch/it/q/cercare/Ak8DAlMDAkZSlcHJpY2XDwMDA?sorting=newest&page=1"
CHECK_INTERVAL = 20  # ogni 3 minuti
NOTIFIED_ADS_FILE = "notified_ads.json"
# --- FINE CONFIGURAZIONE ---

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_notified_ads():
    if not os.path.exists(NOTIFIED_ADS_FILE):
        return set()
    try:
        with open(NOTIFIED_ADS_FILE, 'r') as f:
            data = json.load(f)
            return set(data) if isinstance(data, list) else set()
    except Exception:
        return set()

def save_notified_ads(ad_ids):
    with open(NOTIFIED_ADS_FILE, 'w') as f:
        json.dump(list(ad_ids), f)

def fetch_latest_ads():
    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920x1080")
    options.add_argument("--lang=it-IT")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        driver.get(TARGET_URL)
        time.sleep(6)  # Attendi il caricamento JS

        ads_elements = driver.find_elements(By.XPATH, '//div[@data-private-srp-listing-item-id]')
        results = []

        for ad in ads_elements:
            try:
                ad_id = ad.get_attribute("data-private-srp-listing-item-id")
                link_elem = ad.find_element(By.TAG_NAME, 'a')
                link = link_elem.get_attribute("href")
                title = ad.find_element(By.TAG_NAME, 'h2').text.strip()
                price = ad.find_element(By.XPATH, ".//span[contains(text(), 'Gratis') or contains(text(), 'CHF')]").text.strip()

                # cerca immagine
                try:
                    img_elem = ad.find_element(By.TAG_NAME, "img")
                    image = img_elem.get_attribute("src")
                except:
                    image = None  # fallback se non trova l'immagine
                    
                results.append({
                    "id": ad_id,
                    "title": title,
                    "price": price,
                    "link": f"https://www.tutti.ch{link}" if link.startswith('/') else link,
                    "image": image
                })
            except Exception as e:
                logging.warning(f"Errore parsing annuncio: {e}")
                continue


        return results

    except Exception as e:
        logging.error(f"Errore Selenium: {e}")
        return []

    finally:
        driver.quit()


async def send_telegram_notification(bot, ad):
    message = (
        f"<b>🔥 Nuovo Annuncio su tutti.ch!</b>\n\n"
        f"<b>Titolo:</b> {ad['title']}\n"
        f"<b>Prezzo:</b> {ad['price']}\n"
        f"<a href=\"{ad['link']}\">➡️ Vedi Annuncio</a>"
    )
    try:
        # invia l'immagine con la descrizione sotto
        await bot.send_photo(
            chat_id=TELEGRAM_CHAT_ID,
            photo=ad['image'],
            caption=message,
            parse_mode='HTML'
        )
        logging.info(f"Notifica con immagine inviata per: {ad['title']}")
    except Exception as e:
        logging.error(f"Errore invio Telegram: {e}")


async def main():
    bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
    async with bot:
        logging.info(f"Bot attivo. Monitoraggio di: {TARGET_URL}")
        notified_ad_ids = load_notified_ads()
        logging.info(f"Caricati {len(notified_ad_ids)} ID notificati.")

        while True:
            ads = fetch_latest_ads()
            new_found = False

            for ad in ads:
                if ad['id'] not in notified_ad_ids:
                    await send_telegram_notification(bot, ad)
                    notified_ad_ids.add(ad['id'])
                    new_found = True
                    await asyncio.sleep(1)

            if new_found:
                save_notified_ads(notified_ad_ids)
            else:
                logging.info("Nessun nuovo annuncio.")

            logging.info(f"Prossimo controllo tra {CHECK_INTERVAL} secondi.")
            await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Terminato.")
