#!/usr/bin/env python
import os
import sys
from importlib import import_module

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.insert(0, root_dir)

def test_crawl():
    session_module = import_module("app.db.session")
    crawler_module = import_module("app.services.crawler_service")
    
    get_standalone_db = getattr(session_module, "get_standalone_db")
    CrawlerService = getattr(crawler_module, "CrawlerService")
    
    db = get_standalone_db()
    
    url = "https://topdev.vn/detail-jobs/project-manager-rte-cong-ty-tnhh-capgemini-viet-nam-2090110?src=home&medium=superhotjobs"
    
    print(f"🔍 Bắt đầu cào: {url}\n")
    
    try:
        result = CrawlerService.crawl_job(db, url)
        print("\n✅ Crawl thành công! Dữ liệu lưu:")
        print(f"   📌 Tiêu đề: {result.get('title')}")
        print(f"   🏢 Công ty: {result.get('company_name')}")
        print(f"   📍 Địa điểm: {result.get('location')}")
        print(f"   💰 Lương: {result.get('salary_range')}")
        print(f"   🔧 Kỹ năng: {result.get('job_requirements')}")
        print(f"   📄 Link: {result.get('source_url')}")
        print(f"   🌐 Nguồn: {result.get('source_website')}")
    except Exception as e:
        print(f"❌ Lỗi crawl: {e}")
    finally:
        db.close()
        print("\n✨ Xong! Dữ liệu đã lưu vào bảng 'jobs'")

if __name__ == "__main__":
    test_crawl()
