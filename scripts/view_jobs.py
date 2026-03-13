#!/usr/bin/env python
import os
import sys
from importlib import import_module

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.insert(0, root_dir)

def view_jobs():
    session_module = import_module("app.db.session")
    models_module = import_module("app.models.job")
    
    get_standalone_db = getattr(session_module, "get_standalone_db")
    Job = getattr(models_module, "Job")
    
    db = get_standalone_db()
    
    jobs = db.query(Job).order_by(Job.job_id.desc()).limit(5).all()
    
    print(f"\n📊 Danh sách {len(jobs)} job mới nhất trong DB:\n")
    print("-" * 120)
    
    for idx, job in enumerate(jobs, 1):
        skills_text = job.job_requirements or "Không có"
        skills_list = [item.strip() for item in skills_text.split(",") if item.strip()] if job.job_requirements else []

        print(f"\n{idx}. 🆔 ID: {job.job_id}")
        print(f"   📌 Tiêu đề: {job.title}")
        print(f"   🏢 Công ty: {job.company_name}")
        print(f"   📍 Địa điểm: {job.location}")
        print(f"   💰 Lương: {job.salary_range if job.salary_range else 'Không rõ'}")
        print(f"   🌐 Nguồn: {job.source_website}")
        print(f"   🔗 URL: {job.source_url}")
        print(f"   📅 Lưu vào: {job.created_at}")
        if skills_list:
            print(f"   🔧 Kỹ năng ({len(skills_list)}): {', '.join(skills_list)}")
        else:
            print(f"   🔧 Kỹ năng: {skills_text}")
        print(f"   📄 Mô tả: {job.job_description[:100] if job.job_description else 'Không có'}...")
    
    print("\n" + "-" * 120)
    print(f"✅ Tổng cộng: {len(jobs)} job trong 5 mới nhất\n")
    
    db.close()

if __name__ == "__main__":
    view_jobs()
