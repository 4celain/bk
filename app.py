"""
디시인사이드 크롤링 API 서버 (보안 강화 버전)
- API Key 인증 추가
- Render/Railway 등에 무료 배포 가능
"""

from flask import Flask, jsonify, request
import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime

app = Flask(__name__)

# ============================================================
# 📌 설정 - 환경변수에서 API Key 가져오기
# ============================================================

# Render 대시보드 > Environment에서 설정하세요
API_SECRET_KEY = os.environ.get("API_SECRET_KEY", "default-secret-key-change-me")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://gall.dcinside.com/",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"'
}

# ============================================================
# 📌 API Key 인증 함수
# ============================================================

def verify_api_key():
    """요청의 API Key 검증"""
    provided_key = request.headers.get("X-API-Key") or request.args.get("api_key")
    
    if not provided_key:
        return False, "API Key가 필요합니다"
    
    if provided_key != API_SECRET_KEY:
        return False, "잘못된 API Key입니다"
    
    return True, None

# ============================================================
# 📌 크롤링 함수
# ============================================================

def crawl_dcinside(gallery_id: str, page: int = 1, recommend_only: bool = True) -> dict:
    """디시인사이드 갤러리 크롤링"""
    try:
        if recommend_only:
            url = f"https://gall.dcinside.com/mgallery/board/lists/?id={gallery_id}&exception_mode=recommend&page={page}"
        else:
            url = f"https://gall.dcinside.com/mgallery/board/lists/?id={gallery_id}&page={page}"
        
        session = requests.Session()
        response = session.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
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
                
            except Exception as e:
                print(f"게시글 파싱 에러: {e}")
                continue
        
        return {
            'success': True,
            'count': len(posts),
            'posts': posts,
            'crawledAt': datetime.now().isoformat()
        }
        
    except requests.exceptions.RequestException as e:
        return {'success': False, 'error': f'요청 에러: {str(e)}', 'posts': []}
    except Exception as e:
        return {'success': False, 'error': f'크롤링 에러: {str(e)}', 'posts': []}

# ============================================================
# 📌 API 엔드포인트
# ============================================================

@app.route('/')
def home():
    return jsonify({
        'status': 'ok',
        'message': '디시인사이드 크롤링 API 서버 (보안 버전)',
        'auth_required': True,
        'endpoints': {
            '/crawl': 'GET - 갤러리 크롤링 (API Key 필요)',
            '/health': 'GET - 서버 상태 확인'
        }
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/crawl')
def crawl():
    """
    갤러리 크롤링 API (인증 필요)
    
    헤더:
    - X-API-Key: API 비밀키
    
    쿼리 파라미터:
    - gallery_id: 갤러리 ID (필수)
    - page: 페이지 번호 (선택, 기본값: 1)
    - recommend_only: 개념글만 (선택, 기본값: true)
    """
    # API Key 검증
    is_valid, error_msg = verify_api_key()
    if not is_valid:
        return jsonify({'success': False, 'error': error_msg}), 401
    
    gallery_id = request.args.get('gallery_id', 'thesingularity')
    page = request.args.get('page', 1, type=int)
    recommend_only = request.args.get('recommend_only', 'true').lower() == 'true'
    
    result = crawl_dcinside(gallery_id, page, recommend_only)
    return jsonify(result)

# ============================================================
# 📌 실행
# ============================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
