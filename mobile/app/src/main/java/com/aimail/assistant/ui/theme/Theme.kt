package com.aimail.assistant.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext

private val LightColorScheme = lightColorScheme(
    primary = Primary,
    onPrimary = OnPrimary,
    primaryContainer = Color(0xFFDCEBFF),
    onPrimaryContainer = Color(0xFF001D3D),
    surface = Surface,
    onSurface = Color(0xFF0F172A),
    surfaceVariant = Color(0xFFEFF4FF),
    background = Surface,
    onBackground = Color(0xFF0F172A),
    error = SpamColor,
)

private val DarkColorScheme = darkColorScheme(
    primary = Color(0xFF90B8FF),
    onPrimary = Color(0xFF001D3D),
    primaryContainer = PrimaryDark,
    surface = SurfaceDark,
    onSurface = Color(0xFFE2E8F0),
    surfaceVariant = Color(0xFF1E293B),
    background = SurfaceDark,
    onBackground = Color(0xFFE2E8F0),
    error = Color(0xFFFF8080),
)

@Composable
fun AiMailTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit,
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = AppTypography,
        content = content,
    )
}
