package com.aimail.assistant.ui.orders

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aimail.assistant.data.model.CurrencyStats
import com.aimail.assistant.data.model.OrderItem
import com.aimail.assistant.data.repository.MailRepository
import com.aimail.assistant.data.repository.Result
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class OrdersUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val orders: List<OrderItem> = emptyList(),
    val totalOrders: Int = 0,
    val totalRevenue: Double = 0.0,
    val byCurrency: List<CurrencyStats> = emptyList(),
)

@HiltViewModel
class OrdersViewModel @Inject constructor(
    private val repository: MailRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(OrdersUiState())
    val uiState: StateFlow<OrdersUiState> = _uiState

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val ordersDeferred = async { repository.getOrders() }
            val statsDeferred = async { repository.getOrderStats() }

            val ordersResult = ordersDeferred.await()
            val statsResult = statsDeferred.await()

            val orders = when (ordersResult) {
                is Result.Success -> ordersResult.data.items
                is Result.Error -> {
                    _uiState.value = _uiState.value.copy(isLoading = false, error = ordersResult.message)
                    return@launch
                }
            }

            val stats = when (statsResult) {
                is Result.Success -> statsResult.data
                is Result.Error -> null
            }

            _uiState.value = OrdersUiState(
                isLoading = false,
                orders = orders,
                totalOrders = stats?.totalOrders ?: orders.size,
                totalRevenue = stats?.totalRevenue ?: 0.0,
                byCurrency = stats?.byCurrency ?: emptyList(),
            )
        }
    }
}
