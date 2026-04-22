package com.aimail.assistant.ui.dashboard

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aimail.assistant.data.model.CategoryStats
import com.aimail.assistant.data.repository.MailRepository
import com.aimail.assistant.data.repository.Result
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class DashboardUiState(
    val isLoading: Boolean = false,
    val isProcessing: Boolean = false,
    val total: Int = 0,
    val byCategory: List<CategoryStats> = emptyList(),
    val processMessage: String? = null,
    val error: String? = null,
) {
    val invoiceCount get() = byCategory.firstOrNull { it.category == "invoice" }?.count ?: 0
    val importantCount get() = byCategory.firstOrNull { it.category == "important" }?.count ?: 0
    val spamCount get() = byCategory.firstOrNull { it.category == "spam" }?.count ?: 0
    val otherCount get() = byCategory.firstOrNull { it.category == "other" }?.count ?: 0
}

@HiltViewModel
class DashboardViewModel @Inject constructor(
    private val repository: MailRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(DashboardUiState())
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    init {
        loadStats()
    }

    fun loadStats() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            when (val result = repository.getStats()) {
                is Result.Success -> _uiState.update {
                    it.copy(
                        isLoading = false,
                        total = result.data.total,
                        byCategory = result.data.byCategory,
                    )
                }
                is Result.Error -> _uiState.update {
                    it.copy(isLoading = false, error = result.message)
                }
            }
        }
    }

    fun processMails() {
        viewModelScope.launch {
            _uiState.update { it.copy(isProcessing = true, processMessage = null, error = null) }
            when (val result = repository.processMails()) {
                is Result.Success -> {
                    _uiState.update {
                        it.copy(isProcessing = false, processMessage = result.data.message)
                    }
                    loadStats()
                }
                is Result.Error -> _uiState.update {
                    it.copy(isProcessing = false, error = result.message)
                }
            }
        }
    }

    fun clearMessage() = _uiState.update { it.copy(processMessage = null, error = null) }
}
