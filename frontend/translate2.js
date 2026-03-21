const fs = require('fs');

const more_replacements = {
    "Yêu cầu SIA phân tích dữ liệu, hoặc tìm kiếm...": "Ask SIA to analyze data, or search...",
    "Đã kết nối": "Connected",
    "Trợ lý SIA": "SIA Assistant",
    "Tổng quan": "Dashboard",
    "Nguồn dữ liệu": "Data Sources",
    "Khách hàng": "Customers",
    "Quản trị viên": "Admin",
    "Doanh nghiệp": "Enterprise",
    "Vừa xong": "Just now",
    "giờ trước": "hours ago",
    "History hội thoại": "Chat History",
    "Chưa có lịch sử hội thoại": "No chat history",
    "Xóa": "Delete",
    "AI Analysis dữ liệu": "AI Data Analysis",
    "Cuộc hội thoại mới": "New Conversation",
    "Tôi có thể giúp gì cho bạn hôm nay?": "How can I help you today?",
    "Tôi có thể phân tích số liệu tài chính, tra cứu mét khối khách hàng, tìm hiểu sản phẩm hoặc tạo dashboard thống kê.": "I can analyze financial data, lookup customer metrics, explore products, or create statistical dashboards.",
    "Top 5 sản phẩm bán chạy nhất là gì?": "What are the top 5 best-selling products?",
    "Tạo dashboard tổng quan về tình hình kinh doanh": "Create a business overview dashboard",
    "Tạo dashboard báo cáo tình hình kinh doanh tổng quan": "Create a business overview report dashboard",
    "Đã tra cứu": "Queried",
    "Cơ sở dữ liệu": "Database",
    "Tài nguyên tri thức": "Knowledge Base",
    "Đã thực thi...": "Executed...",
    "Đã tạo ": "Created ",
    " biểu đồ trên bảng phân tích": " charts on analytics board",
    " dòng": " rows",
    "Chưa có biểu đồ nào": "No charts available",
    "Hãy đặt câu hỏi để tạo biểu đồ phân tích": "Ask a question to generate analytical charts",
    "Xem biểu đồ": "View chart",
    "Xem bảng dữ liệu": "View data table",
    "History biểu đồ:": "Chart history:",
    "Quản trị Doanh nghiệp": "Enterprise Dashboard",
    "Cập nhật lần cuối: ": "Last updated: ",
    "Làm mới Dữ liệu": "Refresh Data",
    "Đang đồng bộ số liệu...": "Syncing data...",
    "Lỗi: ": "Error: ",
    "Thử lại": "Retry",
    "Tổng đơn hàng": "Total Orders",
    "Giá trị TB/đơn": "Avg Order Value",
    "Tổng khách hàng": "Total Customers",
    "Tổng sản phẩm": "Total Products",
    "Insights từ AI": "AI Insights"
};

const allFiles = [
    "components/layout/Header.tsx",
    "components/layout/Sidebar.tsx",
    "components/agent/ChatInterface.tsx",
    "components/visualizations/DynamicChart.tsx",
    "app/dashboard/page.tsx",
    "app/page.tsx",
];

allFiles.forEach(file => {
    if (fs.existsSync(file)) {
        let content = fs.readFileSync(file, 'utf8');
        Object.keys(more_replacements).forEach(key => {
            content = content.split(key).join(more_replacements[key]);
        });
        fs.writeFileSync(file, content, 'utf8');
        console.log("Updated", file);
    }
});