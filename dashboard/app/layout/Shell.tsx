import {
  Box,
  Flex,
  Avatar,
  HStack,
  IconButton,
  Button,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  MenuDivider,
  useDisclosure,
  useColorModeValue,
  Link,
  Text,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
} from "@chakra-ui/react"
import { HamburgerIcon, CloseIcon } from "@chakra-ui/icons"
import { useCurrentUser } from "app/core/hooks/useCurrentUser"
import NextLink from "next/link"
import Image from "next/image"
import foxImg from "public/fox.png"
import { invoke } from "@blitzjs/rpc"
import logout from "app/auth/mutations/logout"
import Router from "next/router"
import { Suspense } from "react"

function AuthArea() {
  const currentUser = useCurrentUser()

  if (!currentUser) {
    return (
      <NextLink href="/auth/login">
        <Link>Sign In</Link>
      </NextLink>
    )
  }

  return (
    <Menu>
      <MenuButton as={Button} rounded={"full"} variant={"link"} cursor={"pointer"} minW={0}>
        <Avatar
          size={"sm"}
          name={currentUser.name}
          src={currentUser?.profilePictureUrl ?? undefined}
        />
      </MenuButton>
      <MenuList>
        <NextLink href="/settings">
          <MenuItem>Settings</MenuItem>
        </NextLink>
        <MenuDivider />
        <MenuItem
          onClick={async () => {
            await invoke(logout, null)
            Router.push("/auth/login")
          }}
        >
          Sign Out
        </MenuItem>
      </MenuList>
    </Menu>
  )
}

export function Shell(
  props: React.PropsWithChildren<{
    breadcrumbs?: { label: string; href: string }[]
  }>
) {
  return (
    <>
      <Box bg={useColorModeValue("gray.100", "gray.900")} px={8}>
        <Flex h={16} alignItems={"center"} justifyContent={"space-between"}>
          <HStack spacing={8}>
            <NextLink href="/">
              <Image src={foxImg} width={24} height={32} alt="Datafox Logo" />
            </NextLink>
          </HStack>
          <Breadcrumb>
            {props.breadcrumbs?.map((breadcrumb, index) => {
              const isLastItem = index + 1 === props.breadcrumbs?.length
              return (
                <BreadcrumbItem key={index}>
                  <NextLink href={breadcrumb.href}>
                    <BreadcrumbLink
                      isCurrentPage={isLastItem}
                      textDecor={isLastItem ? "underline" : "none"}
                    >
                      {breadcrumb.label}
                    </BreadcrumbLink>
                  </NextLink>
                </BreadcrumbItem>
              )
            })}
          </Breadcrumb>
          <Suspense fallback={<Box />}>
            <AuthArea />
          </Suspense>
        </Flex>
      </Box>

      <Box p={4} maxWidth="800px" margin="0 auto">
        <Suspense fallback={null}>{props.children}</Suspense>
      </Box>
    </>
  )
}
