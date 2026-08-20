package com.bookmgr.android

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.bookmgr.android.data.settings.SettingsRepository
import com.bookmgr.android.ui.BookmgrApp
import com.bookmgr.android.ui.theme.BookmgrTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val settingsRepository = SettingsRepository(applicationContext)
        setContent {
            BookmgrTheme {
                BookmgrApp(settingsRepository)
            }
        }
    }
}
