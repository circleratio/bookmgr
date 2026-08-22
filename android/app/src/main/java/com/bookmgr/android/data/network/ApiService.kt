package com.bookmgr.android.data.network

import com.bookmgr.android.data.model.Book
import com.bookmgr.android.data.model.BookInfo
import com.bookmgr.android.data.model.BookInput
import com.bookmgr.android.data.model.DataResponse
import com.bookmgr.android.data.model.ListResponse
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

interface ApiService {
    @GET("/api/books")
    suspend fun listBooks(
        @Query("q") q: String?,
        @Query("page") page: Int?,
        @Query("page_size") pageSize: Int?,
    ): Response<ListResponse<Book>>

    @GET("/api/books/{id}")
    suspend fun getBook(@Path("id") id: Long): Response<DataResponse<Book>>

    @GET("/api/books/by-isbn/{isbn}")
    suspend fun getBookByIsbn(@Path("isbn") isbn: String): Response<DataResponse<Book>>

    @POST("/api/books")
    suspend fun createBook(@Body input: BookInput): Response<DataResponse<Book>>

    @PUT("/api/books/{id}")
    suspend fun updateBook(@Path("id") id: Long, @Body input: BookInput): Response<DataResponse<Book>>

    @DELETE("/api/books/{id}")
    suspend fun deleteBook(@Path("id") id: Long): Response<Unit>

    @GET("/api/isbn-lookup")
    suspend fun isbnLookup(@Query("isbn") isbn: String): Response<DataResponse<BookInfo>>
}
