import type { Meta, StoryObj } from "@storybook/react-vite";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./tabs";

const meta = {
  title: "UI/Tabs",
  component: Tabs,
  tags: ["autodocs"],
  argTypes: {
    orientation: {
      control: "select",
      options: ["horizontal", "vertical"],
    },
  },
} satisfies Meta<typeof Tabs>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  render: (args) => (
    <Tabs {...args} defaultValue="members" className="w-96">
      <TabsList>
        <TabsTrigger value="members">Members</TabsTrigger>
        <TabsTrigger value="invites">Invites</TabsTrigger>
        <TabsTrigger value="roles">Roles</TabsTrigger>
      </TabsList>
      <TabsContent value="members">
        Manage who belongs to this workspace and what role they hold.
      </TabsContent>
      <TabsContent value="invites">
        Review pending invitations and revoke ones sent by mistake.
      </TabsContent>
      <TabsContent value="roles">
        Configure which permissions each role grants across the workspace.
      </TabsContent>
    </Tabs>
  ),
};

export const LineVariant: Story = {
  render: (args) => (
    <Tabs {...args} defaultValue="members" className="w-96">
      <TabsList variant="line">
        <TabsTrigger value="members">Members</TabsTrigger>
        <TabsTrigger value="invites">Invites</TabsTrigger>
        <TabsTrigger value="roles">Roles</TabsTrigger>
      </TabsList>
      <TabsContent value="members">
        Manage who belongs to this workspace and what role they hold.
      </TabsContent>
      <TabsContent value="invites">
        Review pending invitations and revoke ones sent by mistake.
      </TabsContent>
      <TabsContent value="roles">
        Configure which permissions each role grants across the workspace.
      </TabsContent>
    </Tabs>
  ),
};

export const Vertical: Story = {
  args: {
    orientation: "vertical",
  },
  render: (args) => (
    <Tabs {...args} defaultValue="members" className="w-96">
      <TabsList>
        <TabsTrigger value="members">Members</TabsTrigger>
        <TabsTrigger value="invites">Invites</TabsTrigger>
        <TabsTrigger value="roles">Roles</TabsTrigger>
      </TabsList>
      <TabsContent value="members">
        Manage who belongs to this workspace and what role they hold.
      </TabsContent>
      <TabsContent value="invites">
        Review pending invitations and revoke ones sent by mistake.
      </TabsContent>
      <TabsContent value="roles">
        Configure which permissions each role grants across the workspace.
      </TabsContent>
    </Tabs>
  ),
};

export const WithDisabledTab: Story = {
  render: (args) => (
    <Tabs {...args} defaultValue="members" className="w-96">
      <TabsList>
        <TabsTrigger value="members">Members</TabsTrigger>
        <TabsTrigger value="invites">Invites</TabsTrigger>
        <TabsTrigger value="roles" disabled>
          Roles
        </TabsTrigger>
      </TabsList>
      <TabsContent value="members">
        Manage who belongs to this workspace and what role they hold.
      </TabsContent>
      <TabsContent value="invites">
        Review pending invitations and revoke ones sent by mistake.
      </TabsContent>
    </Tabs>
  ),
};
