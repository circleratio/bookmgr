package com.bookmgr.android.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.bookmgr.android.data.BookRepository
import com.bookmgr.android.data.model.BookInput
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BookFormScreen(
    bookId: Long?,
    repository: BookRepository,
    onSaved: () -> Unit,
    onCancel: () -> Unit,
) {
    var title by remember { mutableStateOf("") }
    var author by remember { mutableStateOf("") }
    var rating by remember { mutableStateOf("") }
    var isbn by remember { mutableStateOf("") }
    var publisher by remember { mutableStateOf("") }
    var publishedDate by remember { mutableStateOf("") }
    var memo by remember { mutableStateOf("") }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var lookupMessage by remember { mutableStateOf<String?>(null) }
    var saving by remember { mutableStateOf(false) }
    var looking by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val isNew = bookId == null

    LaunchedEffect(bookId) {
        if (bookId != null) {
            try {
                val b = repository.get(bookId)
                title = b.title
                author = b.author
                rating = b.rating?.toString() ?: ""
                isbn = b.isbn ?: ""
                publisher = b.publisher ?: ""
                publishedDate = b.publishedDate ?: ""
                memo = b.memo ?: ""
            } catch (e: Exception) {
                errorMessage = e.message
            }
        }
    }

    fun buildInput(): BookInput = BookInput(
        title = title,
        author = author,
        rating = rating.toIntOrNull(),
        memo = memo.ifBlank { null },
        isbn = isbn.ifBlank { null },
        publisher = publisher.ifBlank { null },
        publishedDate = publishedDate.ifBlank { null },
    )

    Scaffold(topBar = { TopAppBar(title = { Text(if (isNew) "新規登録" else "編集") }) }) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
        ) {
            errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error) }

            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    value = isbn,
                    onValueChange = { isbn = it },
                    label = { Text("ISBN") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
                if (isNew) {
                    Spacer(Modifier.width(8.dp))
                    Button(
                        onClick = {
                            scope.launch {
                                looking = true
                                lookupMessage = null
                                try {
                                    val info = repository.isbnLookup(isbn)
                                    if (info.title.isNotBlank()) title = info.title
                                    if (info.author.isNotBlank()) author = info.author
                                    if (info.publisher.isNotBlank()) publisher = info.publisher
                                    if (info.publishedDate.isNotBlank()) publishedDate = info.publishedDate
                                    if (info.isbn.isNotBlank()) isbn = info.isbn
                                    lookupMessage = "取得しました"
                                } catch (e: Exception) {
                                    lookupMessage = e.message ?: "取得に失敗しました"
                                } finally {
                                    looking = false
                                }
                            }
                        },
                        enabled = isbn.isNotBlank() && !looking,
                    ) { Text(if (looking) "取得中..." else "取得") }
                }
            }
            lookupMessage?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            Spacer(Modifier.height(8.dp))

            OutlinedTextField(value = title, onValueChange = { title = it }, label = { Text("書名 *") }, modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(value = author, onValueChange = { author = it }, label = { Text("著者 *") }, modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = rating,
                onValueChange = { if (it.length <= 1 && it.all { c -> c.isDigit() }) rating = it },
                label = { Text("評価 (1-5)") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(value = publisher, onValueChange = { publisher = it }, label = { Text("出版社") }, modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = publishedDate,
                onValueChange = { publishedDate = it },
                label = { Text("出版日 (YYYY-MM-DD)") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = memo,
                onValueChange = { memo = it },
                label = { Text("メモ") },
                minLines = 3,
                modifier = Modifier.fillMaxWidth(),
            )

            Spacer(Modifier.height(16.dp))
            Row {
                Button(
                    onClick = {
                        scope.launch {
                            saving = true
                            errorMessage = null
                            try {
                                if (isNew) repository.create(buildInput()) else repository.update(bookId!!, buildInput())
                                onSaved()
                            } catch (e: Exception) {
                                errorMessage = e.message
                            } finally {
                                saving = false
                            }
                        }
                    },
                    enabled = title.isNotBlank() && author.isNotBlank() && !saving,
                ) { Text(if (saving) "保存中..." else "保存") }
                Spacer(Modifier.width(8.dp))
                TextButton(onClick = onCancel) { Text("キャンセル") }
            }
        }
    }
}
