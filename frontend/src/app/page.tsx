import Link from "next/link";

export default function HomePage() {
  return (
    <main className="relative min-h-screen overflow-hidden">
      {/* Atmosphere */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_20%_10%,#d7ebe8_0%,transparent_50%),radial-gradient(ellipse_at_85%_20%,#cfe3e8_0%,transparent_45%),linear-gradient(165deg,#eef6f5_0%,#e2eeec_45%,#d5e6e4_100%)]"
      />
      <div
        aria-hidden
        className="hero-glow pointer-events-none absolute -left-24 top-10 h-[28rem] w-[28rem] rounded-full bg-[#9ecfc8]/35 blur-3xl"
      />
      <div
        aria-hidden
        className="hero-glow pointer-events-none absolute -right-16 bottom-0 h-[22rem] w-[22rem] rounded-full bg-[#b7d4de]/40 blur-3xl [animation-delay:-4s]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.35] [background-image:linear-gradient(rgba(20,50,58,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(20,50,58,0.04)_1px,transparent_1px)] [background-size:48px_48px]"
      />

      <div className="relative mx-auto flex min-h-screen max-w-5xl flex-col justify-center px-6 py-20 sm:px-10">
        <p className="animate-rise font-sans text-sm font-semibold tracking-[0.22em] text-brand uppercase">
          MedExplain AI
        </p>

        <h1 className="animate-rise-delay mt-5 max-w-3xl font-display text-5xl leading-[1.05] font-semibold tracking-tight text-foreground sm:text-6xl md:text-7xl">
          MedExplain{" "}
          <span className="relative inline-block text-brand-deep">
            AI
            <span
              aria-hidden
              className="brand-underline absolute -bottom-1 left-0 h-1.5 w-full rounded-full"
            />
          </span>
        </h1>

        <p className="animate-rise-delay-2 mt-6 max-w-xl font-sans text-lg leading-relaxed text-foreground/75 sm:text-xl">
          Turn lab reports into clear, plain-language explanations — so you walk
          into your next appointment prepared, not confused.
        </p>

        <div className="animate-rise-delay-2 mt-10 flex flex-wrap items-center gap-4">
          <Link
            href="/upload"
            className="rounded-md bg-brand px-7 py-3.5 font-sans text-base font-semibold text-mist shadow-[0_10px_30px_rgba(15,107,109,0.28)] transition duration-300 hover:-translate-y-0.5 hover:bg-brand-deep focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            Upload Report
          </Link>
          <span className="font-sans text-sm text-foreground/55">
            PDF, JPG, or PNG — up to 15MB
          </span>
        </div>

        <p className="animate-rise-delay-2 mt-16 max-w-2xl border-t border-[var(--line)] pt-5 font-sans text-sm leading-relaxed text-foreground/55">
          Educational tool only. MedExplain AI does not diagnose, prescribe, or
          replace a licensed clinician. Always discuss results with your doctor.
        </p>
      </div>
    </main>
  );
}
