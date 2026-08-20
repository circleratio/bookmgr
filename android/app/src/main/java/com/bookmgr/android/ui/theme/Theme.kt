package com.bookmgr.android.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val Primary = Color(0xFF2C3E50)
private val Background = Color(0xFFF5F5F5)

private val LightColors = lightColorScheme(
    primary = Primary,
    background = Background,
)

private val DarkColors = darkColorScheme(
    primary = Primary,
)

@Composable
fun BookmgrTheme(content: @Composable () -> Unit) {
    val colors = if (isSystemInDarkTheme()) DarkColors else LightColors
    MaterialTheme(colorScheme = colors, content = content)
}
