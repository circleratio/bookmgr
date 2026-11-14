package com.bookmgr.android.data.settings

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "bookmgr_settings")

data class ServerSettings(val baseUrl: String, val apiKey: String) {
    val isConfigured: Boolean get() = baseUrl.isNotBlank() && apiKey.isNotBlank()
}

class SettingsRepository(private val context: Context) {
    private val baseUrlKey = stringPreferencesKey("base_url")

    // API key encrypted with a Keystore-backed key (see ApiKeyCipher).
    private val encryptedApiKeyKey = stringPreferencesKey("api_key_enc")

    // Plaintext API key written by earlier versions; migrated on startup.
    private val legacyApiKeyKey = stringPreferencesKey("api_key")

    val settings: Flow<ServerSettings> = context.dataStore.data.map { prefs ->
        val apiKey = prefs[encryptedApiKeyKey]?.let { ApiKeyCipher.decryptOrNull(it) }
            ?: prefs[legacyApiKeyKey]
            ?: ""
        ServerSettings(
            baseUrl = prefs[baseUrlKey] ?: "",
            apiKey = apiKey,
        )
    }

    suspend fun save(baseUrl: String, apiKey: String) {
        val encrypted = ApiKeyCipher.encrypt(apiKey)
        context.dataStore.edit { prefs ->
            prefs[baseUrlKey] = baseUrl
            prefs[encryptedApiKeyKey] = encrypted
            prefs.remove(legacyApiKeyKey)
        }
    }

    /** Re-saves a plaintext API key from an earlier version in encrypted form. */
    suspend fun migrateLegacyApiKey() {
        context.dataStore.edit { prefs ->
            val legacy = prefs[legacyApiKeyKey] ?: return@edit
            if (prefs[encryptedApiKeyKey] == null && legacy.isNotEmpty()) {
                prefs[encryptedApiKeyKey] = ApiKeyCipher.encrypt(legacy)
            }
            prefs.remove(legacyApiKeyKey)
        }
    }
}
