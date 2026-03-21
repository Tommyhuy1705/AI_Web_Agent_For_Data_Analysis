const fs = require('fs');

const replacements = {
    "Lịch sử": "History",
    "Chat mới": "New Chat",
    "Trợ lý AI": "AI Assistant",
    "Đã kết nối": "Connected",
    "SIA đang suy nghĩ...": "SIA is thinking...",
    "Chi tiết truy vấn": "Query Details",
    "Chưa có tin nhắn nào": "No messages yet",
    "Yêu cầu SIA phân tích dữ liệu, hoặc tìm kiếm...": "Ask SIA to analyze data, or search...",
    "Hãy bắt đầu bằng cách đặt câu hỏi về dữ liệu của bạn!": "Start by asking a question!",
    "Hỏi SIA bất kỳ về số liệu nào...": "Ask SIA anything about data...",
    "AI có thể nhầm lẫn. Hãy xác minh các dữ liệu quan trọng trước khi ra quyết định.": "AI can make mistakes. Verify important data before making decisions.",
    "Trợ lý phân tích dữ liệu": "Data Analysis Assistant",
    "Sao chép truy vấn": "Copy query",
    "Đã sao chép!": "Copied!",
    "Hôm nay": "Today",
    "Hôm qua": "Yesterday",
    "7 ngày trước": "Previous 7 Days",
    "Cũ hơn": "Older",
    "Bảng Phân Tích SIA": "SIA Analytics Dashboard",
    "Sẵn sàng phân tích dữ liệu": "Ready for data analysis",
    "Chọn trợ lý bên trái hoặc nhập câu hỏi để bắt đầu. SIA sẽ tự động phân tích và tạo biểu đồ, cảnh báo.": "Select the assistant or type a question to start. SIA will automatically analyze and generate charts, alerts.",
    "Cảnh báo hệ thống SIA": "SIA System Alert",
    "Hiển thị": "Showing",
    "chỉ số": "metrics",
    "Bảng điều khiển kinh doanh": "Business Dashboard",
    "Tổng quan và dự báo thời gian thực": "Real-time overview and forecasting",
    "Đang tải dữ liệu dashboard...": "Loading dashboard data...",
    "Đang tải dữ liệu...": "Loading data...",
    "Không thể tải dữ liệu": "Failed to load data",
    "Dữ liệu được cập nhật tự động": "Data is updated automatically",
    "Số liệu doanh thu và phân tích tự động cập nhật theo thời gian thực.": "Revenue and analytics figures are updated automatically in real-time.",
    "Làm mới ngay": "Refresh Now",
    "Chưa có dữ liệu cho biểu đồ này": "No data available for this chart",
    "Loại biểu đồ không được hỗ trợ": "Unsupported chart type",
    "Chưa có dữ liệu": "No data",
    "Truy vấn SQL": "SQL Query",
    "Nguồn dữ liệu": "Data Source",
    "Phân tích": "Analysis",
    "Không có cảnh báo mới": "No new alerts",
    "Đang tải...": "Loading...",
    " Insights từ AI": "AI Insights",
    "Tóm tắt SQL": "SQL Summary",
    "Mở rộng": "Expand",
    "Thu gọn": "Collapse",
    "Nhập câu hỏi...": "Type a question...",
};

const files = [
    "components/agent/ChatInterface.tsx",
    "app/page.tsx",
    "app/layout.tsx",
    "app/dashboard/page.tsx",
    "components/visualizations/DynamicChart.tsx",
];

files.forEach(file => {
    if (fs.existsSync(file)) {
        let content = fs.readFileSync(file, 'utf8');
        Object.keys(replacements).forEach(key => {
            content = content.split(key).join(replacements[key]);
        });
        fs.writeFileSync(file, content, 'utf8');
        console.log(`Updated ${file}`);
    }
});

const more_replacements = {
    "tin nhắn": "messages",
    "Analysis doanh thu tháng này so với tháng trước": "Analyze revenue this month vs last month",
    "Top 5 sản phẩm có doanh thu cao nhất": "Top 5 products by revenue",
    "Tổng doanh thu": "Total Revenue",
    "Tổng doanh thu ròng (đã trừ chi phí)": "Net revenue (after costs)",
    "Tổng Đơn Hàng": "Total Orders",
    "Tổng Doanh Thu": "Total Revenue",
    "Giá Trị ĐHK TB": "Avg Order Value",
    "Tổng Khách Hàng": "Total Customers",
    "Tổng Sản Phẩm": "Total Products",
};

files.forEach(file => {
    if (fs.existsSync(file)) {
        let content = fs.readFileSync(file, 'utf8');
        Object.keys(more_replacements).forEach(key => {
            content = content.split(key).join(more_replacements[key]);
        });
        fs.writeFileSync(file, content, 'utf8');
    }
});
