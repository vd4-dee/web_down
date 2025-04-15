# Import các thư viện cần thiết và khởi tạo đối tượng
from full import WebAutomation
import link_report
import schedule
import time
from datetime import datetime
import sys

print("Job is working...")
# Define all variant
from_date = '2025-01-04'
to_date = '2025-13-04'

chunk_size = 2
chunk_size2 = 5
chunk_size3 = 15
chunk_size4 = 10
chunk_size5 = 16

# Khởi tạo đối tượng WebAutomation
driver_path = r"C:\Users\KTLC-KhangVD4\AppData\Local\SeleniumBasic\chromedriver.exe"
download_folder = WebAutomation.create_download_folder()
automation = WebAutomation(driver_path, download_folder)

# Login
automation.login(link_report.link001)

# Tải báo cáo

# automation.download_reports_in_chunks(link.link005, from_date, to_date, 'month')
# automation.download_reports_in_chunks(link.link006, from_date, to_date, 'month')
# automation.download_reports_in_chunks(link.link003, from_date, to_date, 'month')
# automation.download_reports_in_chunks(link.link043, from_date, to_date,chunk_size4)
# automation.download_reports_in_chunks(link.link010, from_date, to_date,chunk_size4)
# automation.download_reports_in_chunks(link.link010, from_date, to_date,chunk_size4)
# automation.download_reports_in_chunks(link.link075, from_date, to_date,chunk_size4)
# automation.download_reports_for_all_regions(link.link030, from_date, to_date)
automation.download_reports_for_all_regions(link_report.link030, from_date, to_date, region_indices = [5])
# automation.download_reports_in_chunks_1(link.link001, from_date, to_date, chunk_size2)
# automation.download_reports_in_chunks_2(link.link002, from_date, to_date, chunk_size2)
# automation.download_reports_in_chunks_28(link.link028, from_date, to_date, chunk_size2)
# automation.download_reports_in_chunks_4x(link.link004, from_date, to_date, chunk_size2)
# automation.download_reports_in_chunks_4n(link.link004, from_date, to_date, chunk_size2)

# Đóng trình duyệt
automation.close()
print("Job completed!")

print("Script has finished execution.")