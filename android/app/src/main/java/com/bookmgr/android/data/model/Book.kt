package com.bookmgr.android.data.model

import com.squareup.moshi.Json

data class Book(
    val id: Long,
    val title: String,
    val author: String,
    val rating: Int?,
    val memo: String?,
    val isbn: String?,
    val publisher: String?,
    @Json(name = "published_date") val publishedDate: String?,
    @Json(name = "created_at") val createdAt: String,
    @Json(name = "updated_at") val updatedAt: String,
)

data class BookInput(
    val title: String,
    val author: String,
    val rating: Int? = null,
    val memo: String? = null,
    val isbn: String? = null,
    val publisher: String? = null,
    @Json(name = "published_date") val publishedDate: String? = null,
)

data class BookInfo(
    val title: String,
    val author: String,
    val publisher: String,
    @Json(name = "published_date") val publishedDate: String,
    val isbn: String,
)

data class Pagination(
    val page: Int,
    @Json(name = "page_size") val pageSize: Int,
    val total: Int,
)

data class DataResponse<T>(val data: T)

data class ListResponse<T>(val data: List<T>, val pagination: Pagination)

data class ErrorBody(val error: ErrorDetail)

data class ErrorDetail(val code: String, val message: String)
