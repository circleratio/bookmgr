package com.bookmgr.android.data.network

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory

/** Thrown when the server responds with a non-2xx status. */
class ApiException(val statusCode: Int, val code: String, message: String) : Exception(message)

fun buildMoshi(): Moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()

/**
 * Server URL and API key are configured at runtime (Settings screen), so
 * the ApiService instance is built per-connection rather than as a static
 * singleton.
 */
fun createApiService(baseUrl: String, apiKey: String): ApiService {
    val moshi = buildMoshi()

    val authInterceptor = Interceptor { chain ->
        val request = chain.request().newBuilder()
            .addHeader("X-API-Key", apiKey)
            .build()
        chain.proceed(request)
    }

    // Redirects are not followed: OkHttp strips only Authorization on a
    // cross-host redirect, so following one would send X-API-Key to the new
    // host. The server never redirects API requests (matching the CLI, which
    // does not follow redirects either); a 3xx surfaces as an ApiException.
    val okHttpClient = OkHttpClient.Builder()
        .addInterceptor(authInterceptor)
        .followRedirects(false)
        .followSslRedirects(false)
        .build()

    val normalizedBaseUrl = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"

    return Retrofit.Builder()
        .baseUrl(normalizedBaseUrl)
        .client(okHttpClient)
        .addConverterFactory(MoshiConverterFactory.create(moshi))
        .build()
        .create(ApiService::class.java)
}
