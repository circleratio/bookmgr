package com.bookmgr.android.ui

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.navigation.compose.rememberNavController
import com.bookmgr.android.data.BookRepository
import com.bookmgr.android.data.network.createApiService
import com.bookmgr.android.data.settings.ServerSettings
import com.bookmgr.android.data.settings.SettingsRepository

@Composable
fun BookmgrApp(settingsRepository: SettingsRepository) {
    val settings by settingsRepository.settings.collectAsState(initial = ServerSettings("", ""))
    val navController = rememberNavController()

    Surface(modifier = Modifier.fillMaxSize()) {
        if (!settings.isConfigured) {
            // First run, or settings were cleared: force setup before showing
            // any book data. onSaved is a no-op — once settings.isConfigured
            // flips to true, this composable recomposes into the NavHost branch.
            SettingsScreen(settingsRepository = settingsRepository, onSaved = {})
        } else {
            val repository = remember(settings) {
                BookRepository(createApiService(settings.baseUrl, settings.apiKey))
            }
            BookmgrNavHost(
                navController = navController,
                repository = repository,
                settingsRepository = settingsRepository,
            )
        }
    }
}
