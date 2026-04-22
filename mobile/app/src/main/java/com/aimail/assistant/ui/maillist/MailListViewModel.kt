package com.aimail.assistant.ui.maillist

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aimail.assistant.data.model.MailCategory
import com.aimail.assistant.data.model.MailSummary
import com.aimail.assistant.data.repository.MailRepository
import com.aimail.assistant.data.repository.Result
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class MailListUiState(
    val isLoading: Boolean = false,
    val mails: List<MailSummary> = emptyList(),
    val selectedCategory: MailCategory = MailCategory.ALL,
    val total: Int = 0,
    val error: String? = null,
)

@HiltViewModel
class MailListViewModel @Inject constructor(
    private val repository: MailRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(MailListUiState())
    val uiState: StateFlow<MailListUiState> = _uiState.asStateFlow()

    init {
        loadMails()
    }

    fun setInitialCategory(category: String) {
        val cat = MailCategory.entries.firstOrNull { it.value == category } ?: MailCategory.ALL
        if (_uiState.value.selectedCategory != cat) {
            _uiState.update { it.copy(selectedCategory = cat) }
            loadMails()
        }
    }

    fun selectCategory(category: MailCategory) {
        _uiState.update { it.copy(selectedCategory = category) }
        loadMails()
    }

    fun loadMails() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            val categoryFilter = _uiState.value.selectedCategory.value.ifBlank { null }
            when (val result = repository.getMails(category = categoryFilter)) {
                is Result.Success -> _uiState.update {
                    it.copy(
                        isLoading = false,
                        mails = result.data.items,
                        total = result.data.total,
                    )
                }
                is Result.Error -> _uiState.update {
                    it.copy(isLoading = false, error = result.message)
                }
            }
        }
    }
}
