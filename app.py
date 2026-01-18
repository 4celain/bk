"""
디시인사이드 크롤링 API 서버
- Render/Railway 등에 무료 배포 가능
- GAS에서 이 API를 호출하여 데이터 수집
"""

from flask import Flask, jsonify, request
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

app = Flask(__name__)

# ============================================================
# 📌 설정
# ============================================================

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
# 📌 크롤링 함수
# ============================================================

def crawl_dcinside(gallery_id: str, page: int = 1, recommend_only: bool = True) -> dict:
    """디시인사이드 갤러리 크롤링"""
    try:
        # URL 구성
        if recommend_only:
            url = f"https://gall.dcinside.com/mgallery/board/lists/?id={gallery_id}&exception_mode=recommend&page={page}"
        else:
            url = f"https://gall.dcinside.com/mgallery/board/lists/?id={gallery_id}&page={page}"
        
        # 요청
        session = requests.Session()
        response = session.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        # HTML 파싱
        soup = BeautifulSoup(response.text, 'html.parser')
        
        posts = []
        
        # 게시글 행 추출
        rows = soup.select('tr.ub-content')
        
        for row in rows:
            try:
                # 게시글 번호
                post_id = row.get('data-no', '')
                if not post_id:
                    continue
                
                # 제목
                title_elem = row.select_one('td.gall_tit a')
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                link = title_elem.get('href', '')
                
                # 절대 경로로 변환
                if link.startswith('/'):
                    link = f"https://gall.dcinside.com{link}"
                
                # 날짜
                date_elem = row.select_one('td.gall_date')
                date = date_elem.get('title', '') or date_elem.get_text(strip=True) if date_elem else ''
                
                # 작성자
                writer_elem = row.select_one('td.gall_writer')
                writer = writer_elem.get('data-nick', '') if writer_elem else ''
                
                # 조회수
                count_elem = row.select_one('td.gall_count')
                view_count = count_elem.get_text(strip=True) if count_elem else ''
                
                # 추천수
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
        return {
            'success': False,
            'error': f'요청 에러: {str(e)}',
            'posts': []
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'크롤링 에러: {str(e)}',
            'posts': []
        }

# ============================================================
# 📌 API 엔드포인트
# ============================================================

@app.route('/')
def home():
    return jsonify({
        'status': 'ok',
        'message': '디시인사이드 크롤링 API 서버',
        'endpoints': {
            '/crawl': 'GET - 갤러리 크롤링 (파라미터: gallery_id, page, recommend_only)',
            '/health': 'GET - 서버 상태 확인'
        }
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/crawl')
def crawl():
    """
    갤러리 크롤링 API
    
    쿼리 파라미터:
    - gallery_id: 갤러리 ID (필수, 예: thesingularity)
    - page: 페이지 번호 (선택, 기본값: 1)
    - recommend_only: 개념글만 (선택, 기본값: true)
    """
    gallery_id = request.args.get('gallery_id', 'thesingularity')
    page = request.args.get('page', 1, type=int)
    recommend_only = request.args.get('recommend_only', 'true').lower() == 'true'
    
    result = crawl_dcinside(gallery_id, page, recommend_only)
    return jsonify(result)

# ============================================================
# 📌 실행
# ============================================================

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
