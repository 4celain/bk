"""
[보안 패치 완료] 확장 가능한 크롤링 API 서버 v2.1
- 보안: API Key 강제, 관리자 ID 검증 추가
- 기능: 봇 방지, 텔레그램 제어
"""

from flask import Flask, jsonify, request
import requests
from bs4 import BeautifulSoup
import os
import time
import random
from datetime import datetime
from abc import ABC, abstractmethod

app = Flask(__name__)

# ============================================================
# 📌 설정 (보안 강화: 기본값 삭제)
# ============================================================

# 환경변수가 없으면 서버가 켜지지 않게 강제함 (보안 사고 방지)
try:
    API_SECRET_KEY = os.environ["API_SECRET_KEY"]
    TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
    ADMIN_CHAT_ID = os.environ["ADMIN_CHAT_ID"]
except KeyError as e:
    print(f"❌ 필수 환경변수가 없습니다: {e}")
    print("필수: API_SECRET_KEY, TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID")
    exit(1)

# User-Agent 로테이션 (5개 유지)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
]

# 갤러리 영구 저장 파일 (서버 재시작해도 유지)
import json
GALLERIES_FILE = "/tmp/galleries.json"

def load_galleries():
    """저장된 갤러리 목록 로드"""
    try:
        with open(GALLERIES_FILE, 'r') as f:
            return json.load(f)
    except:
        # 환경변수 또는 기본값
        default = os.environ.get("DEFAULT_GALLERIES", "thesingularity")
        return default.split(",")

def save_galleries(galleries):
    """갤러리 목록 저장"""
    try:
        with open(GALLERIES_FILE, 'w') as f:
            json.dump(galleries, f)
    except:
        pass

CRAWLER_STATE = {
    "enabled": True,
    "galleries": load_galleries()
}

# ============================================================
# 📌 기본 크롤러 클래스
# ============================================================

class BaseCrawler(ABC):
    def __init__(self):
        self.session = requests.Session()
    
    def get_headers(self):
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Upgrade-Insecure-Requests": "1"
        }
    
    def random_delay(self):
        time.sleep(random.uniform(1, 2))
    
    @abstractmethod
    def get_list_url(self, gallery_id, page, recommend_only): pass
    @abstractmethod
    def parse_list(self, html): pass
    @abstractmethod
    def get_detail_url(self, post_id, gallery_id): pass
    @abstractmethod
    def parse_detail(self, html): pass
    
    def crawl_list(self, gallery_id, page=1, recommend_only=True):
        try:
            url = self.get_list_url(gallery_id, page, recommend_only)
            self.random_delay()
            response = self.session.get(url, headers=self.get_headers(), timeout=10)
            response.raise_for_status()
            posts = self.parse_list(response.text)
            return {"success": True, "count": len(posts), "posts": posts}
        except Exception as e:
            return {"success": False, "error": str(e), "posts": []}
    
    def crawl_detail(self, post_id, gallery_id):
        try:
            url = self.get_detail_url(post_id, gallery_id)
            self.random_delay()
            response = self.session.get(url, headers=self.get_headers(), timeout=10)
            response.raise_for_status()
            detail = self.parse_detail(response.text)
            detail["success"] = True
            return detail
        except Exception as e:
            return {"success": False, "error": str(e)}

# ============================================================
# 📌 디시인사이드 크롤러
# ============================================================

class DCInsideCrawler(BaseCrawler):
    def get_list_url(self, gallery_id, page, recommend_only):
        base = f"https://gall.dcinside.com/mgallery/board/lists/?id={gallery_id}&page={page}"
        if recommend_only:
            base += "&exception_mode=recommend"
        return base
    
    def get_detail_url(self, post_id, gallery_id):
        return f"https://gall.dcinside.com/mgallery/board/view/?id={gallery_id}&no={post_id}"
    
    def parse_list(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        posts = []
        for row in soup.select('tr.ub-content'):
            try:
                post_id = row.get('data-no')
                if not post_id:
                    continue
                
                title_elem = row.select_one('td.gall_tit a')
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                link = title_elem.get('href', '')
                if link.startswith('/'):
                    link = "https://gall.dcinside.com" + link
                
                date_elem = row.select_one('td.gall_date')
                date = date_elem.get('title', '') if date_elem else ''
                
                writer_elem = row.select_one('td.gall_writer')
                writer = writer_elem.get('data-nick', '') if writer_elem else ''
                
                # viewCount, recommend 유지
                count_elem = row.select_one('td.gall_count')
                view_count = count_elem.get_text(strip=True) if count_elem else ''
                
                recommend_elem = row.select_one('td.gall_recommend')
                recommend = recommend_elem.get_text(strip=True) if recommend_elem else ''
                
                posts.append({
                    'id': post_id,
                    'title': title,
                    'link': link,
                    'date': date,
                    'writer': writer,
                    'viewCount': view_count,
                    'recommend': recommend
                })
            except:
                continue
        return posts
    
    def parse_detail(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        content_elem = soup.select_one('div.write_div')
        content = content_elem.get_text('\n', strip=True)[:5000] if content_elem else ""
        images = []
        if content_elem:
            for img in content_elem.select('img'):
                src = img.get('src', '')
                if 'dcimg' in src:
                    if src.startswith('//'):
                        src = 'https:' + src
                    images.append(src)
        return {"content": content, "images": images[:20]}

CRAWLERS = {"dcinside": DCInsideCrawler}

# ============================================================
# 📌 헬퍼 함수
# ============================================================

def verify_api_key():
    key = request.headers.get("X-API-Key") or request.args.get("api_key")
    return key and key == API_SECRET_KEY

def send_telegram(text, reply_markup=None):
    try:
        payload = {"chat_id": ADMIN_CHAT_ID, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json=payload,
            timeout=10
        )
    except:
        pass

def get_main_menu():
    """메인 메뉴 인라인 키보드"""
    return {
        "inline_keyboard": [
            [{"text": "📊 상태", "callback_data": "status"}, 
             {"text": "📁 갤러리", "callback_data": "galleries"}],
            [{"text": "⏸️ 정지", "callback_data": "pause"}, 
             {"text": "▶️ 재개", "callback_data": "resume"}],
            [{"text": "❓ 도움말", "callback_data": "help"}]
        ]
    }

def answer_callback(callback_id, text=""):
    """콜백 쿼리 응답"""
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
            json={"callback_query_id": callback_id, "text": text},
            timeout=10
        )
    except:
        pass

# ============================================================
# 📌 API 엔드포인트
# ============================================================

@app.route('/')
def home():
    return jsonify({
        'status': 'ok',
        'message': 'Secure Crawler v2.1',
        'supported_sites': list(CRAWLERS.keys())
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/status')
def status():
    if not verify_api_key():
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify({
        'enabled': CRAWLER_STATE['enabled'],
        'galleries': CRAWLER_STATE['galleries']
    })

@app.route('/crawl')
def crawl():
    if not verify_api_key():
        return jsonify({'error': 'Unauthorized'}), 401
    if not CRAWLER_STATE['enabled']:
        return jsonify({'success': False, 'error': 'Paused'})
    
    site = request.args.get('site', 'dcinside')
    gallery_id = request.args.get('gallery_id', 'thesingularity')
    page = request.args.get('page', 1, type=int)
    
    if site not in CRAWLERS:
        return jsonify({'success': False, 'error': 'Unknown site'})
    
    result = CRAWLERS[site]().crawl_list(gallery_id, page, True)
    result['site'] = site
    result['gallery_id'] = gallery_id
    return jsonify(result)

@app.route('/crawl-detail')
def crawl_detail():
    if not verify_api_key():
        return jsonify({'error': 'Unauthorized'}), 401
    
    site = request.args.get('site', 'dcinside')
    gallery_id = request.args.get('gallery_id')
    post_id = request.args.get('post_id')
    
    if not post_id or not gallery_id:
        return jsonify({'success': False, 'error': 'post_id와 gallery_id 필요'})
    
    if site not in CRAWLERS:
        return jsonify({'success': False, 'error': 'Unknown site'})
    
    return jsonify(CRAWLERS[site]().crawl_detail(post_id, gallery_id))

# ============================================================
# 📌 텔레그램 Webhook (관리자 전용)
# ============================================================

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        
        # 콜백 쿼리 처리 (버튼 클릭)
        callback = data.get('callback_query')
        if callback:
            callback_id = callback.get('id')
            chat_id = str(callback.get('from', {}).get('id', ''))
            action = callback.get('data', '')
            
            if chat_id != str(ADMIN_CHAT_ID):
                return jsonify({'ok': True})
            
            answer_callback(callback_id)
            
            if action == 'status':
                status_text = f"🤖 <b>크롤러 상태</b>\n\n"
                status_text += f"상태: {'✅ 동작중' if CRAWLER_STATE['enabled'] else '⏸️ 정지'}\n"
                status_text += f"갤러리: {', '.join(CRAWLER_STATE['galleries'])}"
                send_telegram(status_text, get_main_menu())
            elif action == 'galleries':
                gall_text = "📁 <b>갤러리 목록</b>\n\n"
                for i, g in enumerate(CRAWLER_STATE['galleries'], 1):
                    gall_text += f"{i}. {g}\n"
                send_telegram(gall_text, get_main_menu())
            elif action == 'pause':
                CRAWLER_STATE['enabled'] = False
                send_telegram("⏸️ 크롤러 정지됨", get_main_menu())
            elif action == 'resume':
                CRAWLER_STATE['enabled'] = True
                send_telegram("▶️ 크롤러 재개됨", get_main_menu())
            elif action == 'help':
                help_text = "🤖 <b>명령어</b>\n\n"
                help_text += "/menu - 버튼 메뉴\n"
                help_text += "/add [ID] - 갤러리 추가\n"
                help_text += "/remove [ID] - 갤러리 제거"
                send_telegram(help_text, get_main_menu())
            
            return jsonify({'ok': True})
        
        # 일반 메시지 처리
        msg = data.get('message', {})
        chat_id = str(msg.get('chat', {}).get('id', ''))
        text = msg.get('text', '').strip()
        
        if chat_id != str(ADMIN_CHAT_ID):
            return jsonify({'ok': True})
        
        if text == '/start' or text == '/menu':
            send_telegram("🤖 <b>크롤러 제어판</b>\n\n버튼을 눌러 제어하세요:", get_main_menu())
        
        elif text == '/status':
            status_text = f"🤖 <b>크롤러 상태</b>\n\n"
            status_text += f"상태: {'✅ 동작중' if CRAWLER_STATE['enabled'] else '⏸️ 정지'}\n"
            status_text += f"갤러리: {', '.join(CRAWLER_STATE['galleries'])}"
            send_telegram(status_text, get_main_menu())
        
        elif text == '/galleries':
            gall_text = "📁 <b>갤러리 목록</b>\n\n"
            for i, g in enumerate(CRAWLER_STATE['galleries'], 1):
                gall_text += f"{i}. {g}\n"
            send_telegram(gall_text, get_main_menu())
        
        elif text.startswith('/add '):
            gallery_id = text[5:].strip()
            if gallery_id and gallery_id not in CRAWLER_STATE['galleries']:
                CRAWLER_STATE['galleries'].append(gallery_id)
                save_galleries(CRAWLER_STATE['galleries'])  # 저장
                send_telegram(f"✅ 갤러리 추가됨: {gallery_id}", get_main_menu())
            else:
                send_telegram("❌ 이미 존재하거나 잘못된 ID", get_main_menu())
        
        elif text.startswith('/remove '):
            gallery_id = text[8:].strip()
            if gallery_id in CRAWLER_STATE['galleries']:
                CRAWLER_STATE['galleries'].remove(gallery_id)
                save_galleries(CRAWLER_STATE['galleries'])  # 저장
                send_telegram(f"✅ 갤러리 제거됨: {gallery_id}", get_main_menu())
            else:
                send_telegram("❌ 존재하지 않는 갤러리", get_main_menu())
        
        elif text == '/pause':
            CRAWLER_STATE['enabled'] = False
            send_telegram("⏸️ 크롤러 정지됨", get_main_menu())
        
        elif text == '/resume':
            CRAWLER_STATE['enabled'] = True
            send_telegram("▶️ 크롤러 재개됨", get_main_menu())
        
        elif text == '/crawl':
            # 수동 크롤링 트리거 (GAS가 /trigger 엔드포인트를 호출하도록 안내)
            send_telegram("🔄 수동 크롤링을 시작하려면 GAS에서 testCrawling()을 실행하세요.\n\n또는 Apps Script에서 직접 실행!")
        
        elif text == '/help':
            help_text = "🤖 <b>명령어</b>\n\n"
            help_text += "/menu - 버튼 메뉴\n"
            help_text += "/add [ID] - 갤러리 추가\n"
            help_text += "/remove [ID] - 갤러리 제거\n"
            help_text += "/crawl - 수동 크롤링 안내"
            send_telegram(help_text, get_main_menu())
        
        return jsonify({'ok': True})
    except:
        return jsonify({'ok': True})

# ============================================================
# 📌 실행
# ============================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
