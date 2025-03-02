/** Variances are types which do not conform to the current event pattern */

export interface TokenConfigSuccess {
  status: "ok" | number;
  token: string;
}

interface TokenConfigError {
  status: 401;
}

type TokenConfig = TokenConfigSuccess | TokenConfigError;

export interface InitConfig {
  action: "initialize";
  args: {
    AGENT: string;
    CONFIRMATION_MODE: boolean;
    LANGUAGE: string;
    LLM_API_KEY: string;
    LLM_MODEL: string;
  };
  token?: string;
  token_type?: 'github' | 'gitlab';
  latest_event_id?: unknown; // Not sure what this is
}

// Bare minimum event type sent from the client
interface LocalUserMessageAction {
  action: "message";
  args: {
    content: string;
    image_urls: string[];
  };
}

export type OpenHandsVariance =
  | TokenConfig
  | InitConfig
  | LocalUserMessageAction;
