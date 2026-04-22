package com.aimail.assistant.data.model

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class MailSummary(
    val id: Int,
    val uid: String,
    val subject: String,
    val sender: String,
    val category: String,
    val confidence: Double,
    @Json(name = "has_attachments") val hasAttachments: Boolean,
    @Json(name = "email_date") val emailDate: String,
    @Json(name = "processed_at") val processedAt: String,
)

@JsonClass(generateAdapter = true)
data class MailDetail(
    val id: Int,
    val uid: String,
    val subject: String,
    val sender: String,
    @Json(name = "body_preview") val bodyPreview: String,
    val category: String,
    val confidence: Double,
    @Json(name = "classification_reason") val classificationReason: String,
    @Json(name = "classification_source") val classificationSource: String,
    @Json(name = "has_attachments") val hasAttachments: Boolean,
    @Json(name = "attachment_count") val attachmentCount: Int,
    @Json(name = "raw_size") val rawSize: Int,
    @Json(name = "email_date") val emailDate: String,
    @Json(name = "processed_at") val processedAt: String,
)

@JsonClass(generateAdapter = true)
data class MailListResponse(
    val total: Int,
    val page: Int,
    @Json(name = "page_size") val pageSize: Int,
    val items: List<MailSummary>,
)

@JsonClass(generateAdapter = true)
data class CategoryStats(
    val category: String,
    val count: Int,
)

@JsonClass(generateAdapter = true)
data class StatsResponse(
    val total: Int,
    @Json(name = "by_category") val byCategory: List<CategoryStats>,
)

@JsonClass(generateAdapter = true)
data class ProcessResult(
    val success: Boolean,
    val processed: Int,
    val errors: List<String>,
    val message: String,
)

enum class MailCategory(val value: String, val label: String) {
    ALL("", "All"),
    INVOICE("invoice", "Invoice"),
    IMPORTANT("important", "Important"),
    SPAM("spam", "Spam"),
    OTHER("other", "Other");
}
