import os

def replace_in_file(filepath, replacements):
    with open(filepath, 'r', encoding='utf-8') as file:
        content = file.read()
    
    for old, new in replacements:
        content = content.replace(old, new)
        
    with open(filepath, 'w', encoding='utf-8') as file:
        file.write(content)

# 1. Sidebar.tsx
replace_in_file(
    "frontend/components/layout/Sidebar.tsx",
    [
        ('{ name: "SIA Agent"', '{ name: "Trợ lý SIA"'),
        ('{ name: "Dashboard"', '{ name: "Tổng quan"'),
        ('{ name: "Data Sources"', '{ name: "Nguồn dữ liệu"'),
        ('{ name: "Customers"', '{ name: "Khách hàng"'),
        ('Admin User', 'Quản trị viên'),
        ('Enterprise', 'Doanh nghiệp')
    ]
)

# 2. Header.tsx
replace_in_file(
    "frontend/components/layout/Header.tsx",
    [
        ('placeholder="Ask SIA to analyze revenue, or search tables..."', 'placeholder="Yêu cầu SIA phân tích dữ liệu, hoặc tìm kiếm..."'),
        ('>Connected</span>', '>Đã kết nối</span>')
    ]
)

# 3. page.tsx
replace_in_file(
    "frontend/app/page.tsx",
    [
        ('SIA Analysis Canvas', 'Bảng Phân Tích SIA'),
        ('AI-Generated Insights • {dashboardCharts.length} metrics visualized', 'Insights từ AI • Hiển thị {dashboardCharts.length} chỉ số'),
        ('Connect to your data', 'Sẵn sàng phân tích dữ liệu'),
        ('Select an agent on the left or type a query to begin. SIA will automatically generate visual dashboards, alerts, and insights.', 'Chọn trợ lý bên trái hoặc nhập câu hỏi để bắt đầu. SIA sẽ tự động phân tích và tạo biểu đồ, cảnh báo.'),
        ('SIA System Alert', 'Cảnh báo hệ thống SIA'),
        ('>New</', '>Mới</')
    ]
)

# 4. ChatInterface.tsx
replace_in_file(
    "frontend/components/agent/ChatInterface.tsx",
    [
        ('SIA Assistant', 'Trợ lý SIA'),
        ('Enterprise AI Analyst', 'AI Phân tích dữ liệu'),
        ('How can I help you today?', 'Tôi có thể giúp gì cho bạn hôm nay?'),
        ('I can analyze enterprise revenue data, look up customer metrics, retrieve product insights, or generate comprehensive analytical dashboards.', 'Tôi có thể phân tích số liệu tài chính, tra cứu mét khối khách hàng, tìm hiểu sản phẩm hoặc tạo dashboard thống kê.'),
        ('Analyze revenue performance this month vs last month', 'Phân tích doanh thu tháng này so với tháng trước'),
        ('Find the top 5 highest selling products', 'Top 5 sản phẩm có doanh thu cao nhất'),
        ('Generate a complete executive dashboard', 'Tạo dashboard báo cáo tình hình kinh doanh tổng quan'),
        ("Checked {msg.metadata.action_type === 'sql' ? 'Database' : 'Knowledge Base'}", "Đã tra cứu {msg.metadata.action_type === 'sql' ? 'Cơ sở dữ liệu' : 'Tài nguyên tri thức'}"),
        ('"Executed..."', '"Đã thực thi..."'),
        ('Generated {msg.metadata.allCharts?.length || 0} charts on canvas', 'Đã tạo {msg.metadata.allCharts?.length || 0} biểu đồ trên bảng phân tích'),
        ('Ask SIA to analyze anything...', 'Hỏi SIA bất kỳ về số liệu nào...'),
        ('SIA Enterprise Analyst can make mistakes. Verify critical data.', 'AI có thể nhầm lẫn. Hãy xác minh các dữ liệu quan trọng trước khi ra quyết định.')
    ]
)

# 5. dashboard/page.tsx
replace_in_file(
    "frontend/app/dashboard/page.tsx",
    [
        ('Executive Dashboard', 'Quản trị Doanh nghiệp'),
        ('Real-time analytics and revenue metrics automatically updated by SIA.', 'Số liệu doanh thu và phân tích tự động cập nhật theo thời gian thực.'),
        (' Last synced at: ', ' Cập nhật lần cuối: '),
        ('Refresh Data', 'Làm mới Dữ liệu'),
        ('Synchronizing metrics...', 'Đang đồng bộ số liệu...'),
        ('Error:', 'Lỗi:'),
        ('Try Again', 'Thử lại'),
        ('Total Revenue', 'Tổng doanh thu'),
        ('Total Orders', 'Tổng đơn hàng'),
        ('Avg Order Value', 'Giá trị TB/đơn'),
        ('Total Customers', 'Tổng khách hàng'),
        ('Total Products', 'Tổng sản phẩm')
    ]
)

print("Language patched to Vietnamese successfully!")
