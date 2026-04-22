package com.aimail.assistant.data.api

import com.aimail.assistant.data.model.MailDetail
import com.aimail.assistant.data.model.MailListResponse
import com.aimail.assistant.data.model.OrderStatsResponse
import com.aimail.assistant.data.model.OrdersResponse
import com.aimail.assistant.data.model.ProcessResult
import com.aimail.assistant.data.model.StatsResponse
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

interface MailApiService {

    @GET("mails")
    suspend fun getMails(
        @Query("category") category: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20,
    ): MailListResponse

    @GET("mails/{id}")
    suspend fun getMailDetail(@Path("id") id: Int): MailDetail

    @GET("mails/stats")
    suspend fun getStats(): StatsResponse

    @GET("process-mails")
    suspend fun processMails(): ProcessResult

    @GET("orders")
    suspend fun getOrders(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 50,
    ): OrdersResponse

    @GET("orders/stats")
    suspend fun getOrderStats(): OrderStatsResponse
}
