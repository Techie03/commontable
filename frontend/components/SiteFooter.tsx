// Shared footer: legal links + copyright notice, used by the app shell
// and the landing page.

import Link from "next/link";

export default function SiteFooter() {
  return (
    <footer className="app-footer">
      <div className="container">
        <p>© 2026 CommonTable. All rights reserved.</p>
        <p>
          <Link href="/privacy">Privacy Policy</Link>
          {" · "}
          <Link href="/terms">Terms of Service</Link>
          {" · "}
          <Link href="/copyright">Copyright</Link>
        </p>
      </div>
    </footer>
  );
}
