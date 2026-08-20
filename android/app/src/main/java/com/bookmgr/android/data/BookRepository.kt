package com.bookmgr.android.data

import com.bookmgr.android.data.model.Book
import com.bookmgr.android.data.model.BookInfo
import com.bookmgr.android.data.model.BookInput
import com.bookmgr.android.data.model.ErrorBody
import com.bookmgr.android.data.model.ListResponse
import com.bookmgr.android.data.network.ApiException
import com.bookmgr.android.data.network.ApiService
import com.bookmgr.android.data.network.buildMoshi
import retrofit2.Response

class BookRepository(private val api: ApiService) {
    private val errorAdapter = buildMoshi().adapter(ErrorBody::class.java)

    suspend fun list(q: String?, page: Int?, pageSize: Int?): ListResponse<Book> =
        unwrap(api.listBooks(q, page, pageSize))

    suspend fun get(id: Long): Book = unwrap(api.getBook(id)).data

    suspend fun create(input: BookInput): Book = unwrap(api.createBook(input)).data

    suspend fun update(id: Long, input: BookInput): Book = unwrap(api.updateBook(id, input)).data

    suspend fun delete(id: Long) {
        val response = api.deleteBook(id)
        if (!response.isSuccessful) throw toApiException(response)
    }

    suspend fun isbnLookup(isbn: String): BookInfo = unwrap(api.isbnLookup(isbn)).data

    private fun <T> unwrap(response: Response<T>): T {
        if (response.isSuccessful) {
            return response.body() ?: throw ApiException(response.code(), "EMPTY_BODY", "empty response body")
        }
        throw toApiException(response)
    }

    private fun toApiException(response: Response<*>): ApiException {
        val errorBody = response.errorBody()?.string()
        val parsed = errorBody?.let { runCatching { errorAdapter.fromJson(it) }.getOrNull() }
        return ApiException(
            response.code(),
            parsed?.error?.code ?: "UNKNOWN_ERROR",
            parsed?.error?.message ?: (errorBody ?: "request failed"),
        )
    }
}
