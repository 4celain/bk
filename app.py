"""
확장 가능한 크롤링 API 서버
- 플러그인 구조로 다양한 사이트 지원
- 텔레그램 봇 컨트롤
- 봇 방지 기능
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
# 📌 설정
# ============================================================

API_SECRET_KEY = os.environ.get("API_SECRET_KEY", "default-secret-key-change-me")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "")

# User-Agent 로테이션
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
]

# 크롤러 상태 (메모리 저장, 재시작 시 초기화)
CRAWLER_STATE = {
    "enabled": True,
    "galleries": ["thesingularity"]
}

# ============================================================
# 📌 기본 크롤러 클래스 (추상)
# ============================================================

class BaseCrawler(ABC):
    """모든 크롤러의 기본 클래스"""
    
    def __init__(self):
        self.session = requests.Session()
    
    def get_headers(self):
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
    
    def random_delay(self, min_sec=1, max_sec=3):
        """봇 방지용 랜덤 딜레이"""
        time.sleep(random.uniform(min_sec, max_sec))
    
    @abstractmethod
    def get_list_url(self, gallery_id: str, page: int, recommend_only: bool) -> str:
        """목록 페이지 URL 생성"""
        pass
    
    @abstractmethod
    def parse_list(self, html: str) -> list:
        """목록 페이지 파싱"""
        pass
    
    @abstractmethod
    def get_detail_url(self, post_id: str, gallery_id: str) -> str:
        """상세 페이지 URL 생성"""
        pass
    
    @abstractmethod
    def parse_detail(self, html: str) -> dict:
        """상세 페이지 파싱 (본문 + 이미지)"""
        pass
    
    def crawl_list(self, gallery_id: str, page: int = 1, recommend_only: bool = True) -> dict:
        """목록 크롤링"""
        try:
            url = self.get_list_url(gallery_id, page, recommend_only)
            self.random_delay(0.5, 1.5)
            
            response = self.session.get(url, headers=self.get_headers(), timeout=10)
            response.raise_for_status()
            
            posts = self.parse_list(response.text)
            
            return {
                "success": True,
                "count": len(posts),
                "posts": posts,
                "crawledAt": datetime.now().isoformat()
            }
        except Exception as e:
            return {"success": False, "error": str(e), "posts": []}
    
    def crawl_detail(self, post_id: str, gallery_id: str) -> dict:
        """상세 페이지 크롤링 (본문 + 이미지)"""
        try:
            url = self.get_detail_url(post_id, gallery_id)
            self.random_delay(0.5, 1.5)
            
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
    """디시인사이드 마이너갤러리 크롤러"""
    
    def get_list_url(self, gallery_id: str, page: int, recommend_only: bool) -> str:
        base = f"https://gall.dcinside.com/mgallery/board/lists/?id={gallery_id}&page={page}"
        if recommend_only:
            base += "&exception_mode=recommend"
        return base
    
    def get_detail_url(self, post_id: str, gallery_id: str) -> str:
        return f"https://gall.dcinside.com/mgallery/board/view/?id={gallery_id}&no={post_id}"
    
    def parse_list(self, html: str) -> list:
        soup = BeautifulSoup(html, 'html.parser')
        posts = []
        rows = soup.select('tr.ub-content')
        
        for row in rows:
            try:
                post_id = row.get('data-no', '')
                if not post_id:
                    continue
                
                title_elem = row.select_one('td.gall_tit a')
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                link = title_elem.get('href', '')
                if link.startswith('/'):
                    link = f"https://gall.dcinside.com{link}"
                
                date_elem = row.select_one('td.gall_date')
                date = date_elem.get('title', '') or date_elem.get_text(strip=True) if date_elem else ''
                
                writer_elem = row.select_one('td.gall_writer')
                writer = writer_elem.get('data-nick', '') if writer_elem else ''
                
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
            except Exception:
                continue
        
        return posts
    
    def parse_detail(self, html: str) -> dict:
        soup = BeautifulSoup(html, 'html.parser')
        
        # 본문 추출
        content_elem = soup.select_one('div.write_div')
        content = ""
        if content_elem:
            # 텍스트만 추출
            content = content_elem.get_text(separator='\n', strip=True)
        
        # 이미지 URL 추출
        images = []
        if content_elem:
            for img in content_elem.select('img'):
                src = img.get('src', '')
                if src and 'dcimg' in src:
                    if src.startswith('//'):
                        src = 'https:' + src
                    images.append(src)
        
        return {
            "content": content[:5000],  # 최대 5000자
            "images": images[:10]  # 최대 10개
        }


# ============================================================
# 📌 크롤러 레지스트리
# ============================================================

CRAWLERS = {
    "dcinside": DCInsideCrawler
}

def get_crawler(site: str) -> BaseCrawler:
    """사이트별 크롤러 인스턴스 반환"""
    crawler_class = CRAWLERS.get(site)
    if not crawler_class:
        raise ValueError(f"지원하지 않는 사이트: {site}")
    return crawler_class()


# ============================================================
# 📌 API Key 인증
# ============================================================

def verify_api_key():
    provided_key = request.headers.get("X-API-Key") or request.args.get("api_key")
    if not provided_key:
        return False, "API Key가 필요합니다"
    if provided_key != API_SECRET_KEY:
        return False, "잘못된 API Key입니다"
    return True, None


# ============================================================
# 📌 텔레그램 유틸
# ============================================================

def send_telegram_message(chat_id: str, text: str):
    """텔레그램 메시지 전송"""
    if not TELEGRAM_BOT_TOKEN:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=10)
        return True
    except:
        return False


# ============================================================
# 📌 API 엔드포인트
# ============================================================

@app.route('/')
def home():
    return jsonify({
        'status': 'ok',
        'message': '확장 가능 크롤링 API 서버',
        'version': '2.0',
        'supported_sites': list(CRAWLERS.keys()),
        'endpoints': {
            '/crawl': 'GET - 목록 크롤링',
            '/crawl-detail': 'GET - 상세 크롤링 (본문+이미지)',
            '/status': 'GET - 상태 확인',
            '/health': 'GET - 헬스체크',
            '/webhook': 'POST - 텔레그램 Webhook'
        }
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/status')
def status():
    is_valid, error = verify_api_key()
    if not is_valid:
        return jsonify({'success': False, 'error': error}), 401
    
    return jsonify({
        'success': True,
        'enabled': CRAWLER_STATE['enabled'],
        'galleries': CRAWLER_STATE['galleries'],
        'supported_sites': list(CRAWLERS.keys())
    })

@app.route('/crawl')
def crawl():
    is_valid, error = verify_api_key()
    if not is_valid:
        return jsonify({'success': False, 'error': error}), 401
    
    if not CRAWLER_STATE['enabled']:
        return jsonify({'success': False, 'error': '크롤러가 일시정지 상태입니다'})
    
    site = request.args.get('site', 'dcinside')
    gallery_id = request.args.get('gallery_id', 'thesingularity')
    page = request.args.get('page', 1, type=int)
    recommend_only = request.args.get('recommend_only', 'true').lower() == 'true'
    
    try:
        crawler = get_crawler(site)
        result = crawler.crawl_list(gallery_id, page, recommend_only)
        result['site'] = site
        result['gallery_id'] = gallery_id
        return jsonify(result)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/crawl-detail')
def crawl_detail():
    is_valid, error = verify_api_key()
    if not is_valid:
        return jsonify({'success': False, 'error': error}), 401
    
    site = request.args.get('site', 'dcinside')
    gallery_id = request.args.get('gallery_id', 'thesingularity')
    post_id = request.args.get('post_id', '')
    
    if not post_id:
        return jsonify({'success': False, 'error': 'post_id가 필요합니다'})
    
    try:
        crawler = get_crawler(site)
        result = crawler.crawl_detail(post_id, gallery_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)})


# ============================================================
# 📌 텔레그램 Webhook
# ============================================================

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    """텔레그램 명령어 처리"""
    try:
        data = request.get_json()
        message = data.get('message', {})
        chat_id = str(message.get('chat', {}).get('id', ''))
        text = message.get('text', '').strip()
        
        # 관리자 체크 (선택사항)
        # if chat_id != ADMIN_CHAT_ID:
        #     return jsonify({'ok': True})
        
        if text == '/status':
            status_text = f"🤖 <b>크롤러 상태</b>\n\n"
            status_text += f"상태: {'✅ 실행중' if CRAWLER_STATE['enabled'] else '⏸️ 일시정지'}\n"
            status_text += f"갤러리: {', '.join(CRAWLER_STATE['galleries'])}\n"
            status_text += f"지원 사이트: {', '.join(CRAWLERS.keys())}"
            send_telegram_message(chat_id, status_text)
        
        elif text == '/galleries':
            gall_text = "📁 <b>갤러리 목록</b>\n\n"
            for i, g in enumerate(CRAWLER_STATE['galleries'], 1):
                gall_text += f"{i}. {g}\n"
            send_telegram_message(chat_id, gall_text)
        
        elif text.startswith('/add '):
            gallery_id = text[5:].strip()
            if gallery_id and gallery_id not in CRAWLER_STATE['galleries']:
                CRAWLER_STATE['galleries'].append(gallery_id)
                send_telegram_message(chat_id, f"✅ 갤러리 추가됨: {gallery_id}")
            else:
                send_telegram_message(chat_id, "❌ 이미 존재하거나 잘못된 ID입니다")
        
        elif text.startswith('/remove '):
            gallery_id = text[8:].strip()
            if gallery_id in CRAWLER_STATE['galleries']:
                CRAWLER_STATE['galleries'].remove(gallery_id)
                send_telegram_message(chat_id, f"✅ 갤러리 제거됨: {gallery_id}")
            else:
                send_telegram_message(chat_id, "❌ 존재하지 않는 갤러리입니다")
        
        elif text == '/pause':
            CRAWLER_STATE['enabled'] = False
            send_telegram_message(chat_id, "⏸️ 크롤링 일시정지됨")
        
        elif text == '/resume':
            CRAWLER_STATE['enabled'] = True
            send_telegram_message(chat_id, "▶️ 크롤링 재개됨")
        
        elif text == '/help':
            help_text = """🤖 <b>명령어 목록</b>

/status - 현재 상태
/galleries - 갤러리 목록
/add [ID] - 갤러리 추가
/remove [ID] - 갤러리 제거
/pause - 크롤링 일시정지
/resume - 크롤링 재개
/help - 도움말"""
            send_telegram_message(chat_id, help_text)
        
        return jsonify({'ok': True})
    
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({'ok': True})


# ============================================================
# 📌 실행
# ============================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
