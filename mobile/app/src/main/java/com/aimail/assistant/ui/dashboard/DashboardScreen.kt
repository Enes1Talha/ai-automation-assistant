package com.aimail.assistant.ui.dashboard

import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.aimail.assistant.data.model.CategoryStats
import com.aimail.assistant.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    onNavigateToMailList: (String) -> Unit,
    viewModel: DashboardViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()

    // Show snackbar for messages
    val snackbarHostState = remember { SnackbarHostState() }
    LaunchedEffect(uiState.processMessage) {
        uiState.processMessage?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearMessage()
        }
    }
    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar("Error: $it")
            viewModel.clearMessage()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("AI Mail Assistant", style = MaterialTheme.typography.titleLarge)
                        Text("Email Intelligence Dashboard", style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.loadStats() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                ),
            )
        },
    ) { padding ->
        if (uiState.isLoading) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        } else {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .verticalScroll(rememberScrollState())
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                // Hero card — total
                TotalEmailsCard(total = uiState.total)

                // Category stat cards
                Text("By Category", style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold)

                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    StatCard(
                        modifier = Modifier.weight(1f),
                        label = "Invoice",
                        count = uiState.invoiceCount,
                        icon = Icons.Default.Receipt,
                        color = InvoiceColor,
                        onClick = { onNavigateToMailList("invoice") },
                    )
                    StatCard(
                        modifier = Modifier.weight(1f),
                        label = "Important",
                        count = uiState.importantCount,
                        icon = Icons.Default.Star,
                        color = ImportantColor,
                        onClick = { onNavigateToMailList("important") },
                    )
                }
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    StatCard(
                        modifier = Modifier.weight(1f),
                        label = "Spam",
                        count = uiState.spamCount,
                        icon = Icons.Default.Block,
                        color = SpamColor,
                        onClick = { onNavigateToMailList("spam") },
                    )
                    StatCard(
                        modifier = Modifier.weight(1f),
                        label = "Other",
                        count = uiState.otherCount,
                        icon = Icons.Default.Inbox,
                        color = OtherColor,
                        onClick = { onNavigateToMailList("other") },
                    )
                }

                // Chart
                if (uiState.byCategory.isNotEmpty()) {
                    Text("Distribution", style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold)
                    CategoryBarChart(categories = uiState.byCategory, total = uiState.total)
                }

                // Process button
                Spacer(Modifier.height(8.dp))
                Button(
                    onClick = { viewModel.processMails() },
                    enabled = !uiState.isProcessing,
                    modifier = Modifier.fillMaxWidth().height(52.dp),
                    shape = RoundedCornerShape(12.dp),
                ) {
                    if (uiState.isProcessing) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(20.dp),
                            color = MaterialTheme.colorScheme.onPrimary,
                            strokeWidth = 2.dp,
                        )
                        Spacer(Modifier.width(8.dp))
                        Text("Processing...")
                    } else {
                        Icon(Icons.Default.PlayArrow, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("Process New Emails", fontWeight = FontWeight.SemiBold)
                    }
                }
            }
        }
    }
}

@Composable
private fun TotalEmailsCard(total: Int) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Primary),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(
                    Brush.horizontalGradient(listOf(Primary, PrimaryDark))
                )
                .padding(24.dp)
        ) {
            Column {
                Text("Total Processed", color = Color.White.copy(alpha = 0.8f),
                    style = MaterialTheme.typography.bodyMedium)
                Text(
                    text = total.toString(),
                    color = Color.White,
                    style = MaterialTheme.typography.headlineLarge,
                    fontWeight = FontWeight.Bold,
                )
                Text("emails classified by AI", color = Color.White.copy(alpha = 0.7f),
                    style = MaterialTheme.typography.bodySmall)
            }
            Icon(
                Icons.Default.Email,
                contentDescription = null,
                modifier = Modifier.align(Alignment.CenterEnd).size(56.dp),
                tint = Color.White.copy(alpha = 0.2f),
            )
        }
    }
}

@Composable
private fun StatCard(
    modifier: Modifier = Modifier,
    label: String,
    count: Int,
    icon: ImageVector,
    color: Color,
    onClick: () -> Unit,
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(14.dp),
        onClick = onClick,
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface,
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .clip(CircleShape)
                    .background(color.copy(alpha = 0.15f)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(icon, contentDescription = null, tint = color, modifier = Modifier.size(20.dp))
            }
            Text(
                text = count.toString(),
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold,
            )
            Text(text = label, style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
        }
    }
}

@Composable
private fun CategoryBarChart(categories: List<CategoryStats>, total: Int) {
    val categoryColors = mapOf(
        "invoice" to InvoiceColor,
        "important" to ImportantColor,
        "spam" to SpamColor,
        "other" to OtherColor,
    )

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            categories.sortedByDescending { it.count }.forEach { stat ->
                val color = categoryColors[stat.category] ?: OtherColor
                val fraction = if (total > 0) stat.count.toFloat() / total else 0f
                val animatedFraction by animateFloatAsState(
                    targetValue = fraction,
                    animationSpec = tween(durationMillis = 800, easing = EaseOutCubic),
                    label = "bar_${stat.category}",
                )
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Row(
                        Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Text(stat.category.replaceFirstChar { it.uppercase() },
                            style = MaterialTheme.typography.bodyMedium)
                        Text("${stat.count} (${(fraction * 100).toInt()}%)",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
                    }
                    LinearProgressIndicator(
                        progress = { animatedFraction },
                        modifier = Modifier.fillMaxWidth().height(8.dp).clip(CircleShape),
                        color = color,
                        trackColor = color.copy(alpha = 0.1f),
                    )
                }
            }
        }
    }
}
