"""
Zilliz Service - Vector DB for Semantic Layer
Lưu trữ lớp ngữ nghĩa (Semantic Layer) - định nghĩa KPI, Schema.
Dùng cho RAG: Dify Agent quét Zilliz để hiểu cấu trúc bảng.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Zilliz Configuration
ZILLIZ_URI = os.getenv("ZILLIZ_CLOUD_URI", "")
ZILLIZ_API_KEY = os.getenv("ZILLIZ_API_KEY", "")
COLLECTION_NAME = os.getenv("ZILLIZ_COLLECTION", "semantic_layer")


class ZillizService:
    """Service class cho Zilliz Vector DB."""

    def __init__(self):
        self.uri = ZILLIZ_URI
        self.api_key = ZILLIZ_API_KEY
        self.collection = COLLECTION_NAME
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @property
    def is_configured(self) -> bool:
        """Kiểm tra Zilliz đã được cấu hình chưa."""
        return bool(self.uri and self.api_key)

    async def search_semantic(
        self,
        query: str,
        limit: int = 5,
        output_fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Tìm kiếm ngữ nghĩa trong Semantic Layer.

        Args:
            query: Câu truy vấn
            limit: Số kết quả tối đa
            output_fields: Các trường cần trả về

        Returns:
            Danh sách kết quả tìm kiếm
        """
        if not self.is_configured:
            logger.info("Zilliz not configured, returning default schema info")
            return self._get_default_schema_info()

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.uri}/v2/vectordb/entities/search",
                    json={
                        "collectionName": self.collection,
                        "data": [query],
                        "limit": limit,
                        "outputFields": output_fields or [
                            "name", "description", "type", "schema_info", "kpi_definition"
                        ],
                    },
                    headers=self.headers,
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get("data", [])
                else:
                    logger.error(f"Zilliz search error: {response.status_code}")
                    return self._get_default_schema_info()

        except Exception as e:
            logger.error(f"Zilliz search error: {e}")
            return self._get_default_schema_info()

    async def upsert_semantic_data(
        self,
        data: List[Dict[str, Any]]
    ) -> bool:
        """
        Upsert dữ liệu vào Semantic Layer.

        Args:
            data: Danh sách documents cần upsert

        Returns:
            True nếu thành công
        """
        if not self.is_configured:
            logger.info("Zilliz not configured, skipping upsert")
            return False

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.uri}/v2/vectordb/entities/upsert",
                    json={
                        "collectionName": self.collection,
                        "data": data,
                    },
                    headers=self.headers,
                )
                return response.status_code == 200

        except Exception as e:
            logger.error(f"Zilliz upsert error: {e}")
            return False

    def _get_default_schema_info(self) -> List[Dict[str, Any]]:
        """
        Trả về thông tin schema mặc định khi Zilliz chưa được cấu hình.
        Dùng cho Dify Agent để hiểu cấu trúc bảng.
        Tables are in public schema (Supabase PostgREST compatible).
        """
        return [
            {
                "name": "fact_sales",
                "type": "fact_table",
                "description": "Bảng fact chứa giao dịch bán hàng",
                "schema_info": json.dumps({
                    "columns": [
                        {"name": "sale_id", "type": "BIGSERIAL", "description": "ID giao dịch"},
                        {"name": "order_date", "type": "DATE", "description": "Ngày đặt hàng"},
                        {"name": "product_id", "type": "INTEGER", "description": "FK tới dim_products"},
                        {"name": "customer_id", "type": "INTEGER", "description": "FK tới dim_customers"},
                        {"name": "quantity", "type": "INTEGER", "description": "Số lượng"},
                        {"name": "unit_price", "type": "NUMERIC", "description": "Đơn giá"},
                        {"name": "total_amount", "type": "NUMERIC", "description": "Tổng tiền"},
                        {"name": "discount", "type": "NUMERIC", "description": "Phần trăm giảm giá"},
                        {"name": "channel", "type": "VARCHAR", "description": "Kênh bán (online/offline/marketplace)"},
                        {"name": "payment_method", "type": "VARCHAR", "description": "Phương thức thanh toán"},
                    ]
                }),
                "kpi_definition": json.dumps({
                    "total_revenue": "SUM(total_amount)",
                    "avg_order_value": "AVG(total_amount)",
                    "total_orders": "COUNT(*)",
                    "total_quantity": "SUM(quantity)",
                }),
            },
            {
                "name": "dim_products",
                "type": "dimension_table",
                "description": "Bảng dimension sản phẩm",
                "schema_info": json.dumps({
                    "columns": [
                        {"name": "product_id", "type": "SERIAL", "description": "ID sản phẩm"},
                        {"name": "product_name", "type": "VARCHAR", "description": "Tên sản phẩm"},
                        {"name": "category", "type": "VARCHAR", "description": "Danh mục"},
                        {"name": "sub_category", "type": "VARCHAR", "description": "Danh mục con"},
                        {"name": "brand", "type": "VARCHAR", "description": "Thương hiệu"},
                        {"name": "unit_price", "type": "NUMERIC", "description": "Giá niêm yết"},
                    ]
                }),
            },
            {
                "name": "dim_customers",
                "type": "dimension_table",
                "description": "Bảng dimension khách hàng",
                "schema_info": json.dumps({
                    "columns": [
                        {"name": "customer_id", "type": "SERIAL", "description": "ID khách hàng"},
                        {"name": "customer_name", "type": "VARCHAR", "description": "Tên khách hàng"},
                        {"name": "email", "type": "VARCHAR", "description": "Email"},
                        {"name": "segment", "type": "VARCHAR", "description": "Phân khúc (Premium/Standard/Enterprise)"},
                        {"name": "region", "type": "VARCHAR", "description": "Khu vực (Miền Bắc/Trung/Nam)"},
                        {"name": "city", "type": "VARCHAR", "description": "Thành phố"},
                    ]
                }),
            },
            {
                "name": "v_daily_revenue",
                "type": "view",
                "description": "View doanh thu theo ngày",
                "schema_info": json.dumps({
                    "columns": [
                        {"name": "order_date", "type": "DATE"},
                        {"name": "total_orders", "type": "BIGINT"},
                        {"name": "total_quantity", "type": "BIGINT"},
                        {"name": "total_revenue", "type": "NUMERIC"},
                        {"name": "avg_order_value", "type": "NUMERIC"},
                    ]
                }),
            },
            {
                "name": "v_monthly_revenue",
                "type": "view",
                "description": "View doanh thu theo tháng",
                "schema_info": json.dumps({
                    "columns": [
                        {"name": "month", "type": "DATE"},
                        {"name": "total_orders", "type": "BIGINT"},
                        {"name": "total_revenue", "type": "NUMERIC"},
                        {"name": "avg_order_value", "type": "NUMERIC"},
                    ]
                }),
            },
            {
                "name": "v_product_performance",
                "type": "view",
                "description": "View hiệu suất sản phẩm",
                "schema_info": json.dumps({
                    "columns": [
                        {"name": "product_id", "type": "INTEGER"},
                        {"name": "product_name", "type": "VARCHAR"},
                        {"name": "category", "type": "VARCHAR"},
                        {"name": "total_orders", "type": "BIGINT"},
                        {"name": "total_quantity", "type": "BIGINT"},
                        {"name": "total_revenue", "type": "NUMERIC"},
                    ]
                }),
            },
            {
                "name": "v_customer_segment_revenue",
                "type": "view",
                "description": "View doanh thu theo phân khúc khách hàng",
                "schema_info": json.dumps({
                    "columns": [
                        {"name": "segment", "type": "VARCHAR"},
                        {"name": "region", "type": "VARCHAR"},
                        {"name": "total_customers", "type": "BIGINT"},
                        {"name": "total_orders", "type": "BIGINT"},
                        {"name": "total_revenue", "type": "NUMERIC"},
                    ]
                }),
            },
        ]


# Singleton instance
zilliz_service = ZillizService()
