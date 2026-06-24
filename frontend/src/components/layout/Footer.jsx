export default function Footer() {
  const year = new Date().getFullYear()

  return (
    <footer className="relative z-10 flex flex-wrap items-center justify-center gap-2 px-4 py-2.5 sm:py-3 border-t border-gray-200/70 bg-white/60 backdrop-blur-sm text-center">
      <img src="/favicon.png" alt="RDL Technologies" className="w-5 h-5 rounded-md object-contain shadow-sm" />
      <span className="text-sm font-semibold tracking-tight text-gray-900">RDL Technologies</span>
      <span className="hidden sm:inline text-gray-300">|</span>
      <span className="text-[11px] font-medium text-gray-500">Empowering Sales with Intelligent Automation</span>
      <span className="hidden sm:inline text-gray-300">|</span>
      <span className="text-[10px] text-gray-400">&copy; {year} RDL Technologies. All rights reserved.</span>
    </footer>
  )
}
