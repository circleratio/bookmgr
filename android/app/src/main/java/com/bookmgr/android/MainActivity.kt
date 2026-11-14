package com.bookmgr.android

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.lifecycle.lifecycleScope
import com.bookmgr.android.data.settings.SettingsRepository
import com.bookmgr.android.ui.BookmgrApp
import com.bookmgr.android.ui.theme.BookmgrTheme
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val settingsRepository = SettingsRepository(applicationContext)
        lifecycleScope.launch { settingsRepository.migrateLegacyApiKey() }
        setContent {
            BookmgrTheme {
                BookmgrApp(settingsRepository)
            }
        }
    }
}
