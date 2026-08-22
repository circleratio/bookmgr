package com.bookmgr.android.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.bookmgr.android.data.BookRepository
import com.bookmgr.android.data.model.Book
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BookListScreen(
    repository: BookRepository,
    onOpenBook: (Long) -> Unit,
    onCreateNew: () -> Unit,
    onOpenSettings: () -> Unit,
    onScan: () -> Unit,
) {
    var query by remember { mutableStateOf("") }
    var page by remember { mutableIntStateOf(1) }
    var totalPages by remember { mutableIntStateOf(1) }
    var books by remember { mutableStateOf<List<Book>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun load() {
        loading = true
        errorMessage = null
        try {
            val result = repository.list(query.ifBlank { null }, page, null)
            books = result.data
            totalPages = maxOf(1, (result.pagination.total + result.pagination.pageSize - 1) / result.pagination.pageSize)
        } catch (e: Exception) {
            errorMessage = e.message
        } finally {
            loading = false
        }
    }

    LaunchedEffect(page) { load() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("蔵書一覧") },
                actions = {
                    IconButton(onClick = onScan) {
                        Icon(Icons.Default.CameraAlt, contentDescription = "カメラ")
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "設定")
                    }
                },
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = onCreateNew) {
                Icon(Icons.Default.Add, contentDescription = "新規登録")
            }
        },
    ) { padding ->
        Column(modifier = Modifier.padding(padding).fillMaxSize().padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    label = { Text("書名・著者で検索") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(8.dp))
                Button(onClick = { page = 1; scope.launch { load() } }) {
                    Text("検索")
                }
            }
            Spacer(Modifier.height(8.dp))

            errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error) }

            if (loading) {
                Box(modifier = Modifier.fillMaxWidth().weight(1f), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            } else {
                LazyColumn(modifier = Modifier.weight(1f)) {
                    items(books, key = { it.id }) { book ->
                        ListItem(
                            headlineContent = { Text(book.title) },
                            supportingContent = { Text(book.author) },
                            modifier = Modifier.clickable { onOpenBook(book.id) },
                        )
                        HorizontalDivider()
                    }
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                TextButton(onClick = { if (page > 1) page-- }, enabled = page > 1) { Text("前へ") }
                Text("$page / $totalPages", modifier = Modifier.padding(horizontal = 16.dp))
                TextButton(onClick = { if (page < totalPages) page++ }, enabled = page < totalPages) { Text("次へ") }
            }
        }
    }
}
