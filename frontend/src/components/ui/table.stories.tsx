import type { Meta, StoryObj } from "@storybook/react-vite";
import { Badge } from "./badge";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "./table";

const meta = {
  title: "UI/Table",
  component: Table,
  tags: ["autodocs"],
} satisfies Meta<typeof Table>;

export default meta;
type Story = StoryObj<typeof meta>;

const members = [
  { name: "Ada Okafor", email: "ada@propelreview.com", role: "Admin" },
  { name: "Sam Rossilli", email: "sam@propelreview.com", role: "Admin" },
  { name: "Priya Natarajan", email: "priya@propelreview.com", role: "Manager" },
  { name: "Jonas Weber", email: "jonas@propelreview.com", role: "Individual" },
  { name: "Maria Fernandes", email: "maria@propelreview.com", role: "Individual" },
];

export const Default: Story = {
  render: () => (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Email</TableHead>
          <TableHead>Role</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {members.map((member) => (
          <TableRow key={member.email}>
            <TableCell className="font-medium">{member.name}</TableCell>
            <TableCell>{member.email}</TableCell>
            <TableCell>
              <Badge variant={member.role === "Admin" ? "default" : "secondary"}>
                {member.role}
              </Badge>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  ),
};

export const WithCaptionAndFooter: Story = {
  render: () => (
    <Table>
      <TableCaption>Workspace members and their assigned roles.</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Email</TableHead>
          <TableHead>Role</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {members.map((member) => (
          <TableRow key={member.email}>
            <TableCell className="font-medium">{member.name}</TableCell>
            <TableCell>{member.email}</TableCell>
            <TableCell>
              <Badge variant={member.role === "Admin" ? "default" : "secondary"}>
                {member.role}
              </Badge>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
      <TableFooter>
        <TableRow>
          <TableCell colSpan={2}>Total members</TableCell>
          <TableCell>{members.length}</TableCell>
        </TableRow>
      </TableFooter>
    </Table>
  ),
};

export const Empty: Story = {
  render: () => (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Email</TableHead>
          <TableHead>Role</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell colSpan={3} className="text-muted-foreground h-24 text-center">
            No pending invites.
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  ),
};
