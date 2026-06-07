import asyncio,json,logging,random,re
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright
from aiogram import Bot,Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
BOT_TOKEN="8813248099:AAFFLIysH0ecogwe5DOpi3MsRqQc4oVMsbU"
CHAT_ID="777397042"
CHECK_URL="https://munich.pasport.org.ua/solutions/e-queue"
INTERVAL=600
SEEN_FILE=Path("seen_slots.json")
STATUS_FILE=Path("status.json")
logging.basicConfig(level=logging.INFO,format="%(asctime)s %(message)s",handlers=[logging.StreamHandler(),logging.FileHandler("bot.log",encoding="utf-8")])
log=logging.getLogger(__name__)
def load_seen():
 if SEEN_FILE.exists():
  try:return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
  except:pass
 return set()
def save_seen(s):SEEN_FILE.write_text(json.dumps(sorted(s),ensure_ascii=False,indent=2),encoding="utf-8")
def save_status(s):STATUS_FILE.write_text(json.dumps(s,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
def load_status():
 if STATUS_FILE.exists():
  try:return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
  except:pass
 return{"last_check":None,"found":0,"new":0,"error":None}
async def fetch_slots():
 slots=[]
 await asyncio.sleep(random.uniform(1,4))
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=["--no-sandbox","--disable-dev-shm-usage"])
  page=await browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36")
  try:
   await page.goto(CHECK_URL,wait_until="domcontentloaded",timeout=30000)
   await asyncio.sleep(3)
   content=await page.content()
   text=await page.inner_text("body")
   keywords=["записатися","зайняти","доступно","вільно","записаться","available","вільних"]
   has_slots=any(k in text.lower() for k in keywords)
   no_slots_keywords=["немає вільних","нет свободных","no available","черга відсутня","талони відсутні"]
   no_slots=any(k in text.lower() for k in no_slots_keywords)
   log.info("Page loaded. has_slots=%s no_slots=%s",has_slots,no_slots)
   if has_slots and not no_slots:
    date_matches=re.findall(r"\d{1,2}[./]\d{1,2}[./]\d{2,4}",text)
    time_matches=re.findall(r"\d{1,2}:\d{2}",text)
    if date_matches or time_matches:
     for i,d in enumerate(date_matches[:5]):
      t=time_matches[i] if i<len(time_matches) else "—"
      sid=re.sub(r"[^\w]","_",f"{d}_{t}")
      slots.append({"id":sid,"date":d,"time":t,"service":"Вільний талон","url":CHECK_URL})
    else:
     sid=f"general_{datetime.now().strftime('%Y%m%d_%H')}"
     slots.append({"id":sid,"date":"Перевірте сайт","time":"Перевірте сайт","service":"Знайдено ознаки вільних талонів — перевірте сайт!","url":CHECK_URL})
  except Exception as e:log.error("Page error:%s",e);raise
  finally:await browser.close()
 return slots
async def check_and_notify(bot):
 status={"last_check":datetime.now().strftime("%d.%m.%Y %H:%M:%S"),"found":0,"new":0,"error":None}
 try:
  slots=await fetch_slots();status["found"]=len(slots)
  seen=load_seen();new=[s for s in slots if s["id"] not in seen];status["new"]=len(new)
  for s in new:
   await bot.send_message(chat_id=CHAT_ID,text=f"🟢 *Знайдено вільний талон!*\n\n📅 *Дата:* {s['date']}\n🕐 *Час:* {s['time']}\n📋 {s['service']}\n\n🔗 [Записатися зараз]({s['url']})\n\n_{status['last_check']}_",parse_mode="Markdown")
   seen.add(s["id"]);log.info("Notified:%s",s["id"])
  if len(seen)>1000:seen=set(sorted(seen)[-1000:])
  save_seen(seen)
 except Exception as e:status["error"]=str(e);log.error("Error:%s",e)
 save_status(status);return status
async def scheduler(bot):
 while True:
  await asyncio.sleep(max(60,INTERVAL+random.uniform(-90,90)))
  await check_and_notify(bot)
dp=Dispatcher()
@dp.message(Command("start"))
async def cmd_start(m:Message):await m.answer(f"👋 *Бот моніторингу консульства Мюнхен*\n\n🌐 {CHECK_URL}\n⏱ Кожні {INTERVAL//60} хв\n\n/check — перевірити зараз\n/status — статус",parse_mode="Markdown")
@dp.message(Command("check"))
async def cmd_check(m:Message,bot:Bot):
 await m.answer("🔍 Перевіряю (це може зайняти 15-30 сек)...")
 s=await check_and_notify(bot)
 if s.get("error"):await m.answer(f"❌ `{s['error']}`",parse_mode="Markdown")
 elif s["new"]>0:await m.answer(f"✅ Надіслано *{s['new']}* нових слотів!",parse_mode="Markdown")
 elif s["found"]>0:await m.answer("ℹ️ Слоти вже надсилались раніше.")
 else:await m.answer(f"😔 Вільних талонів не знайдено.\n\n{CHECK_URL}")
@dp.message(Command("status"))
async def cmd_status(m:Message):
 s=load_status()
 await m.answer(f"📊 *Статус*\n\n🕐 `{s.get('last_check') or 'не виконувалась'}`\n🔍 Знайдено: *{s.get('found',0)}*\n🆕 Надіслано: *{s.get('new',0)}*\n{'❌ '+s['error'] if s.get('error') else '✅ Помилок немає'}",parse_mode="Markdown")
async def main():
 bot=Bot(token=BOT_TOKEN)
 try:await bot.send_message(chat_id=CHAT_ID,text=f"🚀 *Бот запущено (v2 з Playwright)!*\n\n🌐 {CHECK_URL}\n⏱ Кожні {INTERVAL//60} хв\n\n/check — перевірити зараз",parse_mode="Markdown")
 except Exception as e:log.warning("Startup:%s",e)
 await asyncio.gather(dp.start_polling(bot,allowed_updates=["message"]),scheduler(bot))
if __name__=="__main__":asyncio.run(main())
