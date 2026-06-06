import type { Preview } from "@storybook/react-vite";
import { ThemeProvider } from "../src/components/theme-provider";
import "../src/index.css";

const preview: Preview = {
  decorators: [
    (Story) => (
      <ThemeProvider>
        <div className="bg-background text-foreground min-h-svh p-6">
          <Story />
        </div>
      </ThemeProvider>
    ),
  ],
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    a11y: {
      test: "todo",
    },
  },
};

export default preview;
