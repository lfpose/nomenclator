import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export interface Cluster {
  representative: string;
  member_count: number;
  members: string[];
}

interface TopClustersTableProps {
  clusters: Cluster[];
}

export function TopClustersTable({ clusters }: TopClustersTableProps) {
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

  const toggleExpand = (id: number) => {
    const newExpanded = new Set(expandedIds);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedIds(newExpanded);
  };

  if (clusters.length === 0) {
    return (
      <div className="text-center text-sm text-muted-foreground py-4">
        No clusters found
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[50px]" />
          <TableHead>Representative</TableHead>
          <TableHead className="text-right">Members</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {clusters.map((cluster, index) => {
          const isExpanded = expandedIds.has(index);
          return (
<>
              <TableRow
                onClick={() => toggleExpand(index)}
                className="cursor-pointer"
              >
                <TableCell>
                  {isExpanded ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                </TableCell>
                <TableCell className="font-medium">
                  {cluster.representative}
                </TableCell>
                <TableCell className="text-right">
                  {cluster.member_count}
                </TableCell>
              </TableRow>
              {isExpanded && (
                <TableRow>
                  <TableCell />
                  <TableCell colSpan={2} className="text-muted-foreground">
                    <ul className="list-disc pl-4 space-y-1">
                      {cluster.members.map((member, memberIndex) => (
                        <li key={memberIndex} className="text-sm">
                          {member}
                        </li>
                      ))}
                    </ul>
                  </TableCell>
                </TableRow>
              )}
</>
          );
        })}
      </TableBody>
    </Table>
  );
}
