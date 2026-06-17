import { aboutPages, type AboutPageKey } from '@/content/aboutPages'

type AboutPageProps = {
  page: AboutPageKey
}

export function AboutPage({ page }: AboutPageProps) {
  const content = aboutPages[page]

  return (
    <article className="mx-auto w-full max-w-[800px] px-6 py-10 sm:px-10">
      <header className="border-b border-[color-mix(in_srgb,var(--text)_16%,transparent)] pb-6">
        <h1 className="text-3xl font-bold text-[var(--text)]">{content.title}</h1>
        {content.lastUpdated && (
          <p className="mt-2 text-sm text-[var(--text-muted)]">
            Last updated: {content.lastUpdated}
          </p>
        )}
        {content.introduction && (
          <p className="mt-5 leading-7 text-[var(--text-muted)]">{content.introduction}</p>
        )}
      </header>

      <div className="space-y-8 py-8">
        {content.sections.map((section) => (
          <section key={section.heading}>
            <h2 className="text-xl font-semibold text-[var(--text)]">{section.heading}</h2>
            {section.paragraphs?.map((paragraph) => (
              <p key={paragraph} className="mt-3 whitespace-pre-line leading-7 text-[var(--text-muted)]">
                {paragraph}
              </p>
            ))}
            {section.items && (
              <ul className="mt-3 list-disc space-y-2 pl-5 text-[var(--text-muted)]">
                {section.items.map((item) => (
                  <li key={item} className="pl-1 leading-7">{item}</li>
                ))}
              </ul>
            )}
          </section>
        ))}
      </div>
    </article>
  )
}
