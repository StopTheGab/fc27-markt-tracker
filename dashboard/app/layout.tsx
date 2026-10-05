import type { Metadata, Viewport } from "next";
import "./globals.css";
import { DataProvider } from "@/components/DataProvider";
import { Header } from "@/components/Header";

export const metadata: Metadata = {
  title: "FC 27 Markt-Tracker",
  description: "Kauf- und Verkaufssignale, Marktüberblick und Preisverläufe für EA SPORTS FC 27 Ultimate Team (PlayStation).",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0f1115",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body>
        <DataProvider>
          <Header />
          <main className="wrap main">{children}</main>
          <footer className="wrap footer muted small">
            Preise: PlayStation, Coins. Alle Zeiten in deutscher Zeit (Europe/Berlin). Gewinn nach 5 % EA-Steuer. Keine
            Anlageberatung – Signale sind regelbasiert und können falsch liegen.
          </footer>
        </DataProvider>
      </body>
    </html>
  );
}
