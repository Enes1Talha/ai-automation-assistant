package com.aimail.assistant.data.repository

import com.aimail.assistant.data.api.MailApiService
import com.aimail.assistant.data.model.MailDetail
import com.aimail.assistant.data.model.MailListResponse
import com.aimail.assistant.data.model.OrderStatsResponse
import com.aimail.assistant.data.model.OrdersResponse
import com.aimail.assistant.data.model.ProcessResult
import com.aimail.assistant.data.model.StatsResponse
import javax.inject.Inject
import javax.inject.Singleton

sealed class Result<out T> {
    data class Success<T>(val data: T) : Result<T>()
    data class Error(val message: String, val cause: Throwable? = null) : Result<Nothing>()
}

@Singleton
class MailRepository @Inject constructor(
    private val api: MailApiService,
) {
    suspend fun getMails(
        category: String? = null,
        page: Int = 1,
        pageSize: Int = 20,
    ): Result<MailListResponse> = safeCall {
        api.getMails(category = category?.ifBlank { null }, page = page, pageSize = pageSize)
    }

    suspend fun getMailDetail(id: Int): Result<MailDetail> = safeCall {
        api.getMailDetail(id)
    }

    suspend fun getStats(): Result<StatsResponse> = safeCall {
        api.getStats()
    }

    suspend fun processMails(): Result<ProcessResult> = safeCall {
        api.processMails()
    }

    suspend fun getOrders(page: Int = 1, pageSize: Int = 50): Result<OrdersResponse> = safeCall {
        api.getOrders(page = page, pageSize = pageSize)
    }

    suspend fun getOrderStats(): Result<OrderStatsResponse> = safeCall {
        api.getOrderStats()
    }

    private inline fun <T> safeCall(block: () -> T): Result<T> =
        try {
            Result.Success(block())
        } catch (e: Exception) {
            Result.Error(e.message ?: "Unknown error", e)
        }
}
