package com.bookmgr.android.ui

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.PhotoCamera
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.bookmgr.android.data.BookRepository
import com.bookmgr.android.data.model.Book
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import kotlinx.coroutines.launch

private sealed interface ScanState {
    data object Idle : ScanState
    data object Processing : ScanState
    data class Registered(val book: Book) : ScanState
    data class Error(val message: String) : ScanState
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BarcodeScanScreen(
    repository: BookRepository,
    onBack: () -> Unit,
    onUnregistered: (isbn: String) -> Unit,
    onOpenBook: (Long) -> Unit,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val scope = rememberCoroutineScope()

    var hasCameraPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED,
        )
    }
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted -> hasCameraPermission = granted }

    LaunchedEffect(Unit) {
        if (!hasCameraPermission) permissionLauncher.launch(Manifest.permission.CAMERA)
    }

    var imageCapture by remember { mutableStateOf<ImageCapture?>(null) }
    var state by remember { mutableStateOf<ScanState>(ScanState.Idle) }

    val barcodeScanner = remember {
        BarcodeScanning.getClient(
            BarcodeScannerOptions.Builder()
                .setBarcodeFormats(Barcode.FORMAT_EAN_13, Barcode.FORMAT_EAN_8)
                .build(),
        )
    }
    DisposableEffect(Unit) { onDispose { barcodeScanner.close() } }

    fun handleCapturedImage(image: ImageProxy) {
        val mediaImage = image.image
        if (mediaImage == null) {
            image.close()
            state = ScanState.Error("画像の取得に失敗しました")
            return
        }
        val inputImage = InputImage.fromMediaImage(mediaImage, image.imageInfo.rotationDegrees)
        barcodeScanner.process(inputImage)
            .addOnSuccessListener { barcodes ->
                image.close()
                val isbn = barcodes.firstOrNull()?.rawValue
                if (isbn.isNullOrBlank()) {
                    state = ScanState.Error("バーコードを検出できませんでした")
                    return@addOnSuccessListener
                }
                scope.launch {
                    try {
                        val existing = repository.findByIsbn(isbn)
                        if (existing != null) {
                            state = ScanState.Registered(existing)
                        } else {
                            onUnregistered(isbn)
                        }
                    } catch (e: Exception) {
                        state = ScanState.Error(e.message ?: "登録状況の確認に失敗しました")
                    }
                }
            }
            .addOnFailureListener {
                image.close()
                state = ScanState.Error(it.message ?: "バーコードの解析に失敗しました")
            }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("バーコードスキャン") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "戻る")
                    }
                },
            )
        },
    ) { padding ->
        Box(modifier = Modifier.padding(padding).fillMaxSize()) {
            if (hasCameraPermission) {
                AndroidView(
                    factory = { ctx ->
                        val previewView = PreviewView(ctx)
                        val cameraProviderFuture = ProcessCameraProvider.getInstance(ctx)
                        cameraProviderFuture.addListener({
                            val cameraProvider = cameraProviderFuture.get()
                            val preview = Preview.Builder().build().also {
                                it.setSurfaceProvider(previewView.surfaceProvider)
                            }
                            val capture = ImageCapture.Builder().build()
                            imageCapture = capture
                            try {
                                cameraProvider.unbindAll()
                                cameraProvider.bindToLifecycle(
                                    lifecycleOwner,
                                    CameraSelector.DEFAULT_BACK_CAMERA,
                                    preview,
                                    capture,
                                )
                            } catch (e: Exception) {
                                state = ScanState.Error(e.message ?: "カメラの起動に失敗しました")
                            }
                        }, ContextCompat.getMainExecutor(ctx))
                        previewView
                    },
                    modifier = Modifier.fillMaxSize(),
                )

                FloatingActionButton(
                    onClick = {
                        val capture = imageCapture ?: return@FloatingActionButton
                        state = ScanState.Processing
                        capture.takePicture(
                            ContextCompat.getMainExecutor(context),
                            object : ImageCapture.OnImageCapturedCallback() {
                                override fun onCaptureSuccess(image: ImageProxy) {
                                    handleCapturedImage(image)
                                }

                                override fun onError(exception: ImageCaptureException) {
                                    state = ScanState.Error(exception.message ?: "撮影に失敗しました")
                                }
                            },
                        )
                    },
                    modifier = Modifier.align(Alignment.BottomCenter).padding(24.dp),
                ) {
                    Icon(Icons.Default.PhotoCamera, contentDescription = "シャッター")
                }

                if (state is ScanState.Processing) {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
            } else {
                Column(
                    modifier = Modifier.fillMaxSize().padding(16.dp),
                    verticalArrangement = Arrangement.Center,
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text("バーコードを読み取るにはカメラの権限が必要です")
                }
            }
        }
    }

    val currentState = state
    if (currentState is ScanState.Registered) {
        AlertDialog(
            onDismissRequest = { state = ScanState.Idle },
            title = { Text("登録済みです") },
            text = { Text("このISBNは既に「${currentState.book.title}」として登録されています。") },
            confirmButton = {
                TextButton(onClick = { onOpenBook(currentState.book.id) }) { Text("詳細を見る") }
            },
            dismissButton = {
                TextButton(onClick = { state = ScanState.Idle }) { Text("再スキャン") }
            },
        )
    } else if (currentState is ScanState.Error) {
        AlertDialog(
            onDismissRequest = { state = ScanState.Idle },
            title = { Text("読み取りエラー") },
            text = { Text(currentState.message) },
            confirmButton = {
                TextButton(onClick = { state = ScanState.Idle }) { Text("閉じる") }
            },
        )
    }
}
