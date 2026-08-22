package com.bookmgr.android.ui

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.bookmgr.android.data.BookRepository
import com.bookmgr.android.data.settings.SettingsRepository

@Composable
fun BookmgrNavHost(
    navController: NavHostController,
    repository: BookRepository,
    settingsRepository: SettingsRepository,
) {
    NavHost(navController = navController, startDestination = "list") {
        composable("list") {
            BookListScreen(
                repository = repository,
                onOpenBook = { id -> navController.navigate("detail/$id") },
                onCreateNew = { navController.navigate("form/new") },
                onOpenSettings = { navController.navigate("settings") },
                onScan = { navController.navigate("scan") },
            )
        }
        composable("scan") {
            BarcodeScanScreen(
                repository = repository,
                onBack = { navController.popBackStack() },
                onUnregistered = { isbn ->
                    navController.navigate("form/new?isbn=$isbn") {
                        popUpTo("scan") { inclusive = true }
                    }
                },
                onOpenBook = { id ->
                    navController.navigate("detail/$id") {
                        popUpTo("scan") { inclusive = true }
                    }
                },
            )
        }
        composable(
            "detail/{id}",
            arguments = listOf(navArgument("id") { type = NavType.LongType }),
        ) { backStackEntry ->
            val id = backStackEntry.arguments?.getLong("id") ?: return@composable
            BookDetailScreen(
                bookId = id,
                repository = repository,
                onEdit = { navController.navigate("form/edit/$id") },
                onDeleted = { navController.popBackStack() },
                onBack = { navController.popBackStack() },
            )
        }
        composable(
            "form/new?isbn={isbn}",
            arguments = listOf(navArgument("isbn") { type = NavType.StringType; nullable = true; defaultValue = null }),
        ) { backStackEntry ->
            BookFormScreen(
                bookId = null,
                initialIsbn = backStackEntry.arguments?.getString("isbn"),
                repository = repository,
                onSaved = { navController.popBackStack() },
                onCancel = { navController.popBackStack() },
            )
        }
        composable(
            "form/edit/{id}",
            arguments = listOf(navArgument("id") { type = NavType.LongType }),
        ) { backStackEntry ->
            val id = backStackEntry.arguments?.getLong("id") ?: return@composable
            BookFormScreen(
                bookId = id,
                repository = repository,
                onSaved = { navController.popBackStack() },
                onCancel = { navController.popBackStack() },
            )
        }
        composable("settings") {
            SettingsScreen(
                settingsRepository = settingsRepository,
                onSaved = { navController.popBackStack() },
            )
        }
    }
}
