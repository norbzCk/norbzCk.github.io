import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./app/App";
import { ChatWidget } from "./components/ChatWidget";
import { AuthProvider } from "./features/auth/AuthContext";
import { CartProvider } from "./features/auth/CartContext";
import { ThemeProvider } from "./features/auth/ThemeContext";
import { CartSidebar } from "./features/cart/CartSidebar";
import { ErrorBoundary } from "./components/ErrorBoundary";
import "./styles/global.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <ThemeProvider>
        <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <AuthProvider>
              <QueryClientProvider client={new QueryClient()}>
                <CartProvider>
                  <App />
                  <CartSidebar />
                  <ChatWidget />
                </CartProvider>
              </QueryClientProvider>        
           </AuthProvider>
        </BrowserRouter>
      </ThemeProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);

// Register service worker for PWA functionality
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/service-worker.js')
      .then(registration => {
        console.log('ServiceWorker registration successful with scope: ', registration.scope);
      })
      .catch(err => {
        console.log('ServiceWorker registration failed: ', err);
      });
  });
}
