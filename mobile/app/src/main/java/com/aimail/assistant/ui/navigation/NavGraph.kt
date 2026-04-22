package com.aimail.assistant.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.aimail.assistant.ui.dashboard.DashboardScreen
import com.aimail.assistant.ui.maildetail.MailDetailScreen
import com.aimail.assistant.ui.maillist.MailListScreen

sealed class Screen(val route: String) {
    object Dashboard : Screen("dashboard")
    object MailList : Screen("mails?category={category}") {
        fun createRoute(category: String = "") = "mails?category=$category"
    }
    object MailDetail : Screen("mails/{id}") {
        fun createRoute(id: Int) = "mails/$id"
    }
}

@Composable
fun AiMailNavGraph(
    navController: NavHostController = rememberNavController(),
) {
    NavHost(
        navController = navController,
        startDestination = Screen.Dashboard.route,
    ) {
        composable(Screen.Dashboard.route) {
            DashboardScreen(
                onNavigateToMailList = { category ->
                    navController.navigate(Screen.MailList.createRoute(category))
                },
            )
        }

        composable(
            route = Screen.MailList.route,
            arguments = listOf(
                navArgument("category") {
                    type = NavType.StringType
                    defaultValue = ""
                }
            ),
        ) { backStackEntry ->
            val category = backStackEntry.arguments?.getString("category") ?: ""
            MailListScreen(
                initialCategory = category,
                onMailClick = { id ->
                    navController.navigate(Screen.MailDetail.createRoute(id))
                },
                onBack = { navController.popBackStack() },
            )
        }

        composable(
            route = Screen.MailDetail.route,
            arguments = listOf(
                navArgument("id") { type = NavType.IntType }
            ),
        ) { backStackEntry ->
            val id = backStackEntry.arguments?.getInt("id") ?: return@composable
            MailDetailScreen(
                mailId = id,
                onBack = { navController.popBackStack() },
            )
        }
    }
}
