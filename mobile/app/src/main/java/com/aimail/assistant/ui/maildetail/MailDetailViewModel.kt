package com.aimail.assistant.ui.maildetail

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aimail.assistant.data.model.MailDetail
import com.aimail.assistant.data.repository.MailRepository
import com.aimail.assistant.data.repository.Result
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class MailDetailUiState(
    val isLoading: Boolean = false,
    val mail: MailDetail? = null,
    val error: String? = null,
)

@HiltViewModel
class MailDetailViewModel @Inject constructor(
    private val repository: MailRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(MailDetailUiState())
    val uiState: StateFlow<MailDetailUiState> = _uiState.asStateFlow()

    fun loadMail(id: Int) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            when (val result = repository.getMailDetail(id)) {
                is Result.Success -> _uiState.update {
                    it.copy(isLoading = false, mail = result.data)
                }
                is Result.Error -> _uiState.update {
                    it.copy(isLoading = false, error = result.message)
                }
            }
        }
    }
}
