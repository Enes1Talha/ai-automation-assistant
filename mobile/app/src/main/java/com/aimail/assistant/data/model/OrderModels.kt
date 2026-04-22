package com.aimail.assistant.data.model

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class OrderItem(
    val date: String,
    val sender: String,
    val subject: String,
    @Json(name = "order_number") val orderNumber: String,
    @Json(name = "customer_name") val customerName: String,
    @Json(name = "items_summary") val itemsSummary: String,
    @Json(name = "total_amount") val totalAmount: Double,
    val currency: String,
    @Json(name = "processed_at") val processedAt: String,
)

@JsonClass(generateAdapter = true)
data class OrdersResponse(
    val total: Int,
    val page: Int,
    @Json(name = "page_size") val pageSize: Int,
    val items: List<OrderItem>,
)

@JsonClass(generateAdapter = true)
data class CurrencyStats(
    val currency: String,
    val count: Int,
    val total: Double,
)

@JsonClass(generateAdapter = true)
data class OrderStatsResponse(
    @Json(name = "total_orders") val totalOrders: Int,
    @Json(name = "total_revenue") val totalRevenue: Double,
    @Json(name = "by_currency") val byCurrency: List<CurrencyStats>,
)
