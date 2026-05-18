import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="text-center space-y-4 p-8">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-xl bg-primary/10 text-primary text-2xl font-bold">
          DW
        </div>
        <h1 className="text-4xl font-bold text-foreground">404</h1>
        <h2 className="text-lg font-medium text-foreground">Page not found</h2>
        <p className="text-sm text-muted-foreground max-w-sm mx-auto">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <Link
          href="/"
          className="inline-flex items-center rounded-lg bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          Go to Dashboard
        </Link>
      </div>
    </div>
  );
}
