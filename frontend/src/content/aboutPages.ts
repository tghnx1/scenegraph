export type AboutSection = {
  heading: string
  paragraphs?: string[]
  items?: string[]
}

export type AboutPageContent = {
  title: string
  lastUpdated?: string
  introduction?: string
  sections: AboutSection[]
}

export type AboutPageKey = 'privacy' | 'terms' | 'impressum' | 'contact' | 'cookies'

export const aboutPages: Record<AboutPageKey, AboutPageContent> = {
  privacy: {
    title: 'Privacy Policy',
    lastUpdated: 'June 13, 2026',
    introduction:
      'Scenegraph is an experimental application for exploring relationships between artists, events, venues, promoters, genres, and recommendation signals in the Berlin music scene.',
    sections: [
      {
        heading: 'Who operates this service',
        paragraphs: [
          '[Scenegraph Team]\n[Harzerstraße 42, Neukölln, Berlin]\nEmail: [scenegraph email]',
        ],
      },
      {
        heading: 'Data we process',
        items: [
          'Account information, including username, email address, role, account status, password hash, and account creation date.',
          'Authentication information stored in the browser, including a login token, role, username, user ID, and artist ID.',
          'Recommendation feedback, including selected entities, feedback values, optional reasons, and timestamps.',
          'Technical information needed to operate and secure the service, such as server logs, request metadata, IP addresses, and error information.',
          'Public or imported music-scene information about artists, events, venues, promoters, genres, and source URLs.',
        ],
      },
      {
        heading: 'Why we process data',
        items: [
          'To provide graph exploration, accounts, administration, and recommendation features.',
          'To improve recommendation quality and investigate errors.',
          'To protect, maintain, and secure the application.',
          'To import, normalize, and analyze music-event information.',
        ],
      },
      {
        heading: 'External services',
        paragraphs: [
          'When configured, Scenegraph may use OpenAI or Azure OpenAI to create tags and embeddings. Artist or event text, such as biographies and descriptions, may be sent to the configured provider. Hosting, database, and other infrastructure providers may also process data as needed to operate the service.',
        ],
      },
      {
        heading: 'Local storage and cookies',
        paragraphs: [
          'Scenegraph currently uses browser local storage for login-related values and the selected visual theme. If analytics, advertising, or optional tracking cookies are introduced, this policy and the cookie controls will be updated.',
        ],
      },
      {
        heading: 'Retention and your rights',
        paragraphs: [
          'Account information is retained while an account is active or as needed for administration and security. Depending on applicable law, you may request access, correction, deletion, restriction, objection, or portability of your personal data. Send requests to [scenegraph privacy email].',
        ],
      },
    ],
  },
  terms: {
    title: 'Terms of Service',
    lastUpdated: 'June 13, 2026',
    introduction:
      'These terms apply to the use of Scenegraph, an experimental music-scene graph and recommendation application.',
    sections: [
      {
        heading: 'Purpose of the service',
        paragraphs: [
          'Scenegraph provides tools for browsing artists, events, venues, promoters, genres, and recommendation relationships. The application is a prototype and may change, become unavailable, or contain incomplete information.',
        ],
      },
      {
        heading: 'Accounts',
        paragraphs: [
          'Some features require an account and may be limited by artist, agent, or administrator roles. You are responsible for keeping your credentials secure and must not share access with unauthorized people.',
        ],
      },
      {
        heading: 'Acceptable use',
        items: [
          'Do not attempt to gain unauthorized access to accounts, systems, or data.',
          'Do not disrupt, overload, or damage the application or its infrastructure.',
          'Do not submit unlawful, harmful, or intentionally misleading material.',
          'Do not reuse third-party data in violation of applicable rights or source-platform terms.',
        ],
      },
      {
        heading: 'Recommendations and third-party data',
        paragraphs: [
          'Recommendations, scores, extracted tags, and explanations are generated automatically and may be inaccurate. Imported information remains subject to the rights and terms of its original owners and sources.',
        ],
      },
      {
        heading: 'Availability and liability',
        paragraphs: [
          'The prototype is provided as available, without a guarantee of uninterrupted operation or complete accuracy. Liability is limited only to the extent permitted by applicable law.',
        ],
      },
      {
        heading: 'Contact',
        paragraphs: ['Questions about these terms can be sent to [scenegraph email].'],
      },
    ],
  },
  impressum: {
    title: 'Impressum',
    sections: [
      {
        heading: 'Service provider',
        paragraphs: [
          '[Full name]\n[Street and house number]\n[Postal code and city]\n[Country]',
        ],
      },
      {
        heading: 'Contact',
        paragraphs: ['Email: [scenegraph email]\nPhone: [scenegraph phone number'],
      },
      {
        heading: 'Represented by',
        paragraphs: ['[none yet]'],
      },
      {
        heading: 'Register and tax information',
        paragraphs: [
          '[Register, registration court, and registration number, if applicable]\n[VAT identification number, if applicable]',
        ],
      },
      {
        heading: 'Responsible for content',
        paragraphs: ['[Full name and address, if applicable]'],
      },
      {
        heading: 'Project status',
        paragraphs: [
          'Scenegraph is currently a non-commercial educational and experimental project. This notice must be completed with the operator’s real details before a public deployment.',
        ],
      },
    ],
  },
  contact: {
    title: 'Contact',
    introduction:
      'For questions about Scenegraph, account access, music-scene data, or the project itself, use the contact details below.',
    sections: [
      {
        heading: 'General enquiries',
        paragraphs: ['Email: [scenegraph email]'],
      },
      {
        heading: 'Privacy requests',
        paragraphs: [
          'For access, correction, or deletion requests concerning personal data, email [scenegraph privacy email].',
        ],
      },
      {
        heading: 'Corrections',
        paragraphs: [
          'To report incorrect artist, event, venue, promoter, or relationship information, email [scenegraph data corrections email] and include the relevant name or page URL.',
        ],
      },
      {
        heading: 'Project status',
        paragraphs: [
          'Scenegraph is experimental. Its imported data, inferred relationships, and recommendations may be incomplete or inaccurate.',
        ],
      },
    ],
  },
  cookies: {
    title: 'Cookie Settings',
    introduction: 'Scenegraph currently does not use optional analytics or advertising cookies.',
    sections: [
      {
        heading: 'Browser storage',
        paragraphs: [
          'The application uses local storage to maintain login information and your selected theme. These values support application functionality and are not used for advertising.',
        ],
      },
    ],
  },
}
